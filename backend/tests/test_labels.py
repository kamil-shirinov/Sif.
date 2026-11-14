import numpy as np
import pandas as pd
import pytest

from storm import ingest
from storm.features import pair_features
from storm.detector import load_calendar
from storm.labels import find_storms, label_all, scheduled_event
from tests.conftest import USDJPY_SPOT_ZIP, needs_raw


def _toy_spot(mids, start="2026-07-01 00:00"):
    ts = pd.date_range(start, periods=len(mids), freq="min", tz="UTC")
    mids = np.asarray(mids)
    df = pd.DataFrame({"timestamp": ts})
    for side, adj in (("bid", -0.0005), ("ask", 0.0005), ("mid", 0.0)):
        for f in ("open", "high", "low", "close"):
            df[f"{f}_{side}"] = mids + adj
    return df


def test_toy_drop_is_one_merged_storm():
    rng = np.random.default_rng(0)
    rets = rng.normal(0, 1e-4, 3000)            # ~1 bp per minute
    rets[2000:2030] = -10e-4                    # 30 minutes of -10 bp: about -260 bp
    rets[2100:2110] = -10e-4                    # a second leg 70 minutes later merges in
    mids = 150 * np.cumprod(1 + rets)
    feat = pair_features(_toy_spot(mids), "USDJPY")
    storms = find_storms(feat, "USDJPY")
    assert len(storms) == 1
    s = storms[0]
    assert s["move_bp"] < -300
    # The trough is the lowest mid from onset to the last triggering window (noise may extend it).
    assert feat.index[2109] <= s["trough_utc"] <= feat.index[2109 + 15]
    assert feat["mid"][s["trough_utc"]] <= feat["mid"].iloc[2109]
    assert feat.index[1995] <= s["onset_utc"] <= feat.index[2016]


def test_quiet_series_has_no_storm():
    rng = np.random.default_rng(1)
    mids = 150 * np.cumprod(1 + rng.normal(0, 1e-4, 3000))
    assert find_storms(pair_features(_toy_spot(mids), "USDJPY"), "USDJPY") == []


@needs_raw
def test_finds_30_july_usdjpy_storm():
    df, _ = ingest.read_zip(USDJPY_SPOT_ZIP)
    storms = label_all({"USDJPY": pair_features(df, "USDJPY")})
    hit = storms[storms["storm_id"] == "usdjpy-2026-07-30"]
    assert len(hit) == 1
    s = hit.iloc[0]
    assert abs(s.onset_utc - pd.Timestamp("2026-07-30 13:29", tz="UTC")) <= pd.Timedelta(minutes=2)
    assert s.move_bp == pytest.approx(-290, abs=10)
    assert s.trough_utc == pd.Timestamp("2026-07-30 14:23", tz="UTC")


def _calendar(tmp_path, *rows):
    path = tmp_path / "calendar.csv"
    path.write_text("time_utc,event,region,source_url,verified\n"
                    + "".join(f"{t},{name},US,https://example.org,yes\n" for t, name in rows))
    return load_calendar(path)


def test_scheduled_means_onset_within_15_minutes_of_an_event(tmp_path):
    cal = _calendar(tmp_path, ("2026-07-02T12:30:00Z", "Payrolls"), ("2026-07-02T13:00:00Z", "Later"))
    t = lambda hm: pd.Timestamp(f"2026-07-02 {hm}", tz="UTC")
    assert scheduled_event(t("12:15"), cal) == ("Payrolls", t("12:30"))     # 15 min before: in
    assert scheduled_event(t("12:50"), cal) == ("Later", t("13:00"))        # nearest event wins
    assert scheduled_event(t("12:40"), cal)[0] == "Payrolls"                # 10 min after beats 20 before
    assert scheduled_event(t("12:14"), cal) is None                         # 16 min before: out
    assert scheduled_event(t("13:16"), cal) is None                         # 16 min after: out
    assert scheduled_event(t("12:30"), cal.iloc[0:0]) is None               # empty calendar


def test_label_all_marks_scheduled_and_unscheduled_storms(tmp_path):
    rng = np.random.default_rng(0)
    rets = rng.normal(0, 1e-4, 4000)
    rets[2000:2030] = -10e-4      # onset ~ 2026-07-02 09:20
    rets[3500:3530] = -10e-4      # onset ~ 2026-07-03 10:20, far from any event
    feat = pair_features(_toy_spot(150 * np.cumprod(1 + rets)), "USDJPY")
    storms = find_storms(feat, "USDJPY")
    assert len(storms) == 2
    near = storms[0]["onset_utc"] + pd.Timedelta(minutes=10)
    cal = _calendar(tmp_path, (f"{near:%Y-%m-%dT%H:%M:%SZ}", "US CPI"))
    df = label_all({"USDJPY": feat}, cal)
    assert df["kind"].tolist() == ["scheduled", "unscheduled"]
    assert df["event"].tolist() == ["US CPI", ""]
    assert df["event_utc"].iloc[0] == near and pd.isna(df["event_utc"].iloc[1])
    empty = label_all({"USDJPY": feat}, cal.iloc[0:0])
    assert (empty["kind"] == "unscheduled").all()
