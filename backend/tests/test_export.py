import json

import pytest

from storm import export
from storm.paths import PROCESSED_DIR
from storm.validate import validate_file
from tests.synthetic import write_spot
from tests.test_detector import CFG

HAVE_PROCESSED = all((PROCESSED_DIR / f"{p}_SPOT.parquet").exists() for p in ("EURUSD", "USDJPY", "USDSGD"))
METRICS = {"split": "test: August 2026", "storms": 2, "caught": 1, "median_move_ahead_pct": 55.0,
           "false_alarms_per_day": 0.5}


def _export_all(processed, out, cfg=None):
    ctx = export.load_context(processed, processed / "raw", processed / "no_calendar.csv", cfg)
    return ctx, export.export_all(ctx, out, METRICS)


def test_every_exported_bundle_validates_synthetic(tmp_path):
    ctx, (paths, index, summaries) = _export_all(write_spot(tmp_path / "processed"), tmp_path / "out", CFG)
    assert len(paths) == len(ctx.storms) >= 4
    for p in [*paths, index]:
        assert validate_file(p) == [], p
    ix = json.loads(index.read_text())
    assert [s["file"] for s in ix["storms"]] == [p.name for p in paths]
    assert ix["metrics"] == METRICS
    for p in paths:
        b = json.loads(p.read_text())
        assert b["n"] == 361 and b["storm"]["onset_i"] == 180     # 3 h either side of onset
        assert "restore_i" in b["ships"]["prepared"]
        types = [e["type"] for e in b["events"]]
        if b["ships"]["prepared"]["cut_i"] is not None:
            assert types.count("cut") >= 1 and b["events"][types.index("cut")]["i"] == b["ships"]["prepared"]["cut_i"]


def test_synthetic_storm_against_the_book_cuts_and_restores(tmp_path):
    _, (paths, _, _) = _export_all(write_spot(tmp_path / "processed"), tmp_path / "out", CFG)
    b = json.loads((tmp_path / "out" / "usdjpy-2026-07-20.json").read_text())
    ship = b["ships"]["prepared"]
    assert ship["cut_i"] is not None and ship["restore_i"] is not None and ship["restore_i"] > ship["cut_i"]
    alarm = next(e for e in b["events"] if e["type"] == "alarm")
    assert alarm["i"] == ship["cut_i"] and alarm["move_ahead_pct"] is not None
    # EURUSD up is USD down: danger for the short-EUR leg too.
    e = json.loads((tmp_path / "out" / "eurusd-2026-07-20.json").read_text())
    assert e["ships"]["prepared"]["cut_i"] is not None


@pytest.mark.skipif(not HAVE_PROCESSED, reason="no processed SGX data")
def test_every_exported_bundle_validates_real_data(tmp_path):
    ctx = export.load_context(write_labels=False)
    paths, index, _ = export.export_all(ctx, tmp_path, None)
    assert len(paths) == len(ctx.storms)
    for p in [*paths, index]:
        assert validate_file(p) == [], p
