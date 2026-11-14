import json

import pytest

from storm import export
from storm.paths import PROCESSED_DIR
from storm.ai.verify import verify_numbers
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


def test_export_embeds_a_verified_mock_report_with_the_scheduled_event(tmp_path):
    processed = write_spot(tmp_path / "processed")
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n"
                   "2026-07-20T12:30:00Z,US Consumer Price Index (June 2026),US,https://example.org,yes\n")
    ctx = export.load_context(processed, processed / "raw", cal, CFG)
    paths, index, summaries = export.export_all(ctx, tmp_path / "out", METRICS)
    for p in [*paths, index]:
        assert validate_file(p) == [], p
    kinds = {}
    for p in paths:
        b = json.loads(p.read_text())
        r = b["report"]
        assert r["model"] == "mock" and r["verified"] is True and r["unverified_numbers"] == []
        assert r["inspector"] == {"verdict": "ok", "issues": []}
        assert "synthetic" in r["text"].lower()
        facts = export.report_facts(b)
        assert verify_numbers(r["text"], facts)["verified"]         # every number traces to a fact
        kinds[b["storm_id"]] = b["storm"]["kind"]
        if b["storm"]["kind"] == "scheduled":
            ev = facts["storm"]["scheduled_event"]
            assert b["storm"]["event"] == ev["name"] == "US Consumer Price Index (June 2026)"
            assert ev["time_utc"] == "2026-07-20T12:30:00Z"
            assert ev["onset_minutes_after_event"] == (b["storm"]["onset_i"] - b["storm"]["event_i"])
            watch = [e for e in b["events"] if e["type"] == "watch"]
            assert watch and watch[0]["event"] == ev["name"] and watch[0]["at_i"] == b["storm"]["event_i"]
        else:
            assert "event" not in b["storm"] and "scheduled_event" not in facts["storm"]
    # Onsets 12:17, 12:17 and 12:27 on 20 July are within 15 min of the 12:30 event; the rest are not.
    assert {k for k, v in kinds.items() if v == "scheduled"} == {
        "usdjpy-2026-07-20", "eurusd-2026-07-20", "usdsgd-2026-07-20"}
    assert ctx.storms.set_index("storm_id")["event"]["usdjpy-2026-08-20"] == ""


def test_export_all_keeps_and_re_reports_yahoo_bundles(tmp_path):
    from tests.test_equity import _run
    from storm import equity as eq
    out = tmp_path / "out"
    out.mkdir()
    nvda, _ = eq.build_bundle(_run())
    nvda["report"] = None
    export.write_bundle(nvda, out)
    ctx, (paths, index, summaries) = _export_all(write_spot(tmp_path / "processed"), out, CFG)
    assert out / "nvda-2026-11-12.json" in paths
    b = json.loads((out / "nvda-2026-11-12.json").read_text())
    assert b["report"]["verified"] is True and validate_file(out / "nvda-2026-11-12.json") == []
    assert b["series"] == nvda["series"] and b["ships"] == nvda["ships"]
    ix = json.loads(index.read_text())
    assert "nvda-2026-11-12.json" in [s["file"] for s in ix["storms"]]


def test_index_lists_scenario_bundles_with_their_source_and_leaves_them_alone(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    ctx, _ = _export_all(write_spot(tmp_path / "processed"), out, CFG)
    first = next(p for p in sorted(out.glob("*.json")) if p.name != "index.json")
    sc = json.loads(first.read_text())
    sc.update(storm_id="whatif-1", source="scenario", report=None)
    text = json.dumps(sc)
    (out / "whatif-1.json").write_text(text)
    _, (paths, index, _) = _export_all(write_spot(tmp_path / "processed"), out, CFG)
    assert (out / "whatif-1.json").read_text() == text           # never rewritten
    assert out / "whatif-1.json" not in paths
    ix = json.loads(index.read_text())
    assert validate_file(index) == []
    entry = next(s for s in ix["storms"] if s["file"] == "whatif-1.json")
    assert entry["source"] == "scenario"
    assert {s["source"] for s in ix["storms"] if s["file"] != "whatif-1.json"} == {"sgx"}
