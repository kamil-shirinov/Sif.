import pandas as pd

from storm import tune
from tests.synthetic import AUGUST, write_spot
from tests.test_detector import EMPTY

GRID = {"move_windows": [[1, 3, 5]], "w_comove": [0.0], "storm_on": [0.6, 0.8],
        "storm_minutes": [1, 2], "calm_off": [0.25]}


def _comparable(out):
    return [(r["order"], r["config"], r["metrics"]) for r in out["ranked"]]


def test_tuning_never_reads_august_rows(tmp_path, monkeypatch):
    seen = []
    real = tune.pair_features

    def spy(spot, pair):
        seen.append(spot["timestamp"].max())
        return real(spot, pair)

    monkeypatch.setattr(tune, "pair_features", spy)
    clean = tune.tune(write_spot(tmp_path / "clean"), GRID, EMPTY)
    poisoned = tune.tune(write_spot(tmp_path / "poisoned", poison_august=True), GRID, EMPTY)

    assert seen and max(seen) < AUGUST                                  # no August row reaches features
    assert all(hi < AUGUST for _, hi in poisoned["feature_range"].values())
    assert (poisoned["storms"]["onset_utc"] < AUGUST).all()
    assert _comparable(poisoned) == _comparable(clean)                  # wild August prices change nothing
    assert clean["best"]["config"] == poisoned["best"]["config"]
    assert clean["best"]["metrics"]["storms"] == 3                      # the three July storms


def test_squall_level_sits_below_storm_level(tmp_path):
    best = tune.tune(write_spot(tmp_path), GRID, EMPTY)["best"]["config"]
    assert best["calm_off"] <= best["squall_on"] < best["storm_on"]


def test_rank_prefers_caught_then_fewer_false_alarms():
    a = {"caught": 3, "false_alarms_per_day": 0.9, "median_move_ahead_pct": 60.0, "median_minutes_to_alarm": 2.0}
    b = {**a, "caught": 2, "false_alarms_per_day": 0.1}
    c = {**a, "false_alarms_per_day": 0.5}
    assert sorted([a, b, c], key=tune.rank_key) == [c, a, b]


def test_split_bounds():
    assert tune.TUNE_START == pd.Timestamp("2026-07-01", tz="UTC") and tune.TUNE_END == AUGUST
