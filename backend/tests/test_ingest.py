import io
import zipfile

import pandas as pd

from storm import ingest
from tests.conftest import USDJPY_SPOT_ZIP, needs_raw

SPOT_HEADER = ("timestamp,settlement_date,open_bid,open_ask,open_mid,high_bid,high_ask,high_mid,"
               "low_bid,low_ask,low_mid,close_bid,close_ask,close_mid")


def _spot_csv(times):
    rows = [SPOT_HEADER] + [f"{t}+00:00,2026-08-03" + ",1.0" * 12 for t in times]
    return "\n".join(rows) + "\n"


def _make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)


def test_parse_name():
    assert ingest.parse_name("USDJPY_USD_SPOT_SPOT_1000000_20260701-20260831.zip") == ("USDJPY", "SPOT")
    assert ingest.parse_name("EURUSD_EUR_FORWARD_1W_1000000_20260701-20260831.zip") == ("EURUSD", "1W")


def test_duplicates_and_gaps_on_toy_zip(tmp_path):
    # Thursday: 3 bars, a duplicate, then a 10-minute hole. Friday 21:00 -> Sunday 19:01 is the weekend.
    thu = ["2026-07-30 10:00:00", "2026-07-30 10:01:00", "2026-07-30 10:01:00", "2026-07-30 10:11:00"]
    fri = ["2026-07-31 21:00:00"]
    sun = ["2026-08-02 19:01:00", "2026-08-02 19:02:00"]
    raw = tmp_path / "raw"
    raw.mkdir()
    _make_zip(raw / "USDJPY_USD_SPOT_SPOT_1000000_20260730-20260802.zip", {
        "a_20260802.csv": _spot_csv(sun),   # out of order on purpose
        "a_20260730.csv": _spot_csv(thu),
        "a_20260731.csv": _spot_csv(fri),
    })
    reports = ingest.ingest(raw, tmp_path / "out")
    (rep,) = reports
    assert (rep.pair, rep.tenor, rep.rows, rep.duplicates) == ("USDJPY", "SPOT", 6, 1)
    # The 10-minute hole and the Thursday->Friday overnight hole are reported; the weekend is not.
    assert [(g.after_utc[:16], g.minutes) for g in rep.gaps] == [
        ("2026-07-30 10:01", 10.0),
        ("2026-07-30 10:11", pd.Timedelta("1 days 10:49:00").total_seconds() / 60),
    ]
    df = pd.read_parquet(tmp_path / "out" / "USDJPY_SPOT.parquet")
    assert str(df["timestamp"].dt.tz) == "UTC"
    assert df["timestamp"].is_monotonic_increasing and df["timestamp"].is_unique
    assert (tmp_path / "out" / "ingest_report.json").exists()


def test_forward_keeps_only_close_columns(tmp_path):
    header = ("timestamp,settlement_date,close_bid,close_mid,close_mid_fp,close_mid_all_in,open_mid")
    text = header + "\n2026-07-30 10:00:00+00:00,2026-09-03,1,2,3,4,5\n"
    path = tmp_path / "USDJPY_USD_FORWARD_1M_1000000_20260701-20260831.zip"
    _make_zip(path, {"x.csv": text})
    df, rep = ingest.read_zip(path)
    assert rep.tenor == "1M"
    assert list(df.columns) == ingest.FORWARD_COLUMNS


@needs_raw
def test_real_usdjpy_spot_zip():
    df, rep = ingest.read_zip(USDJPY_SPOT_ZIP)
    assert rep.pair == "USDJPY" and rep.tenor == "SPOT"
    assert len(df.columns) == 14 and str(df["timestamp"].dt.tz) == "UTC"
    assert rep.duplicates == 0 and df["timestamp"].is_unique
    assert rep.first_utc.startswith("2026-07-01") and rep.last_utc.startswith("2026-08-31")
    # Only the two long daily-rollover holes (7 and 9 July) exceed 5 minutes outside weekends.
    assert [g.after_utc[:10] for g in rep.gaps] == ["2026-07-07", "2026-07-09"]
