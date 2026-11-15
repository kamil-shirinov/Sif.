"""Every number in README.md's results tables equals metrics.json.

The tables are parsed by scripts/readme_results.py (see its docstring for the format).
data/processed/metrics.json is the reference whenever it exists; docs/results_snapshot.json is a
committed copy of just the values the README cites, so this runs on a machine without SGX's
data too. `python scripts/readme_results.py --write-snapshot` refreshes the snapshot.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import readme_results as rr  # noqa: E402

README = ROOT / "README.md"
needs_readme = pytest.mark.skipif(not README.exists(), reason="README.md not in this checkout")
needs_metrics = pytest.mark.skipif(not rr.METRICS.exists(), reason="data/processed/metrics.json not present (SGX data is not committed)")


def test_parser_reads_prefix_columns_and_formats():
    text = "\n".join([
        "<!-- metrics-table: methods.{col}. -->",
        "| metric | `v1` | `naive` | meaning |",
        "|---|---|---|---|",
        "| `caught` | 4 | 1 | storms |",
        "| `median_move_ahead_pct` | 57.4% | +6.2 | share |",
        "<!-- metrics-table: -->",
        "| metric | `value` |",
        "|---|---|",
        "| `policy.prepared.final_equity_usd` | $1,033,659 |",
    ])
    cells = [(p, n) for p, _, _, n in rr.parse_tables(text)]
    assert cells == [("methods.v1.caught", 4.0), ("methods.naive.caught", 1.0),
                     ("methods.v1.median_move_ahead_pct", 57.4), ("methods.naive.median_move_ahead_pct", 6.2),
                     ("policy.prepared.final_equity_usd", 1033659.0)]


def test_check_catches_a_changed_number_a_missing_path_and_a_non_number():
    ref = {"methods": {"v1": {"caught": 4, "alarmed": 6}}}
    ok = "<!-- metrics-table: methods.{col}. -->\n| m | `v1` |\n|---|---|\n| `caught` | 4 |\n| `alarmed` | 6 |\n"
    assert rr.check(ok, ref) == []
    assert len(rr.check(ok.replace("| 4 |", "| 5 |"), ref)) == 1
    assert len(rr.check(ok.replace("`alarmed`", "`missing`"), ref)) == 1
    assert len(rr.check(ok.replace("| 6 |", "| six |"), ref)) == 1
    assert rr.check("no tables here", ref), "a README without a results table must fail"


def test_marker_can_name_another_source_and_compares_rounded_to_the_cells_decimals():
    text = "\n".join([
        "<!-- metrics-table[oos1]: display.totals.{col}.metrics. -->",
        "| metric | `events` | `all` |",
        "|---|---|---|",
        "| `storms` | 11 | 23 |",
        "| `median_move_ahead_pct` | 57.3 | 43.4 |",
    ])
    cells = [(p, n) for p, _, _, n in rr.parse_tables(text)]
    assert cells[0] == ("oos1::display.totals.events.metrics.storms", 11.0)
    extra = {"oos1": {"display": {"totals": {"events": {"metrics": {"storms": 11, "median_move_ahead_pct": 57.31}},
                                             "all": {"metrics": {"storms": 23, "median_move_ahead_pct": 43.44}}}}}}
    assert rr.check(text, {}, extra=extra) == []                      # 57.31 shows as 57.3
    assert len(rr.check(text.replace("57.3", "57.4"), {}, extra=extra)) == 1
    assert len(rr.check(text, {}, extra={})) == 4                     # a missing source is reported, not skipped
    flat = {path: value for (path, _), value in zip(cells, [11, 23, 57.31, 43.44])}
    assert rr.check(text, flat, flat=True) == []                      # the committed snapshot works the same way


@needs_readme
def test_readme_has_results_tables_and_links_the_definitions():
    text = README.read_text()
    assert rr.parse_tables(text), "README.md has no metrics-table"
    assert "docs/metrics.md" in text


@needs_readme
@needs_metrics
def test_readme_numbers_equal_metrics_json():
    problems = rr.check(README.read_text(), json.loads(rr.METRICS.read_text()), extra=rr.load_extra())
    assert not problems, "\n".join(problems)


@needs_readme
def test_readme_numbers_equal_the_committed_snapshot():
    assert rr.SNAPSHOT.exists(), "docs/results_snapshot.json missing: run scripts/readme_results.py --write-snapshot"
    problems = rr.check(README.read_text(), json.loads(rr.SNAPSHOT.read_text()), flat=True)
    assert not problems, "\n".join(problems)


@needs_readme
@needs_metrics
def test_snapshot_is_current_with_metrics_json():
    want = rr.snapshot_from(json.loads(rr.METRICS.read_text()), README.read_text(), rr.load_extra())
    assert json.loads(rr.SNAPSHOT.read_text()) == want, "stale: run scripts/readme_results.py --write-snapshot"
