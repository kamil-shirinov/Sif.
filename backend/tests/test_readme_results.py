"""Every number in the results tables of README.md and docs/results.md equals its result file.

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


def docs_text() -> str:
    """README.md and docs/results.md together: the long tables moved from the README to docs/results.md."""
    return "\n".join(text for _, text in rr.docs())


def cited() -> list[str]:
    return [p for p, *_ in rr.all_cells()]
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
    problems = rr.check_all(json.loads(rr.METRICS.read_text()), extra=rr.load_extra())
    assert not problems, "\n".join(problems)


@needs_readme
def test_readme_numbers_equal_the_committed_snapshot():
    assert rr.SNAPSHOT.exists(), "docs/results_snapshot.json missing: run scripts/readme_results.py --write-snapshot"
    problems = rr.check_all(json.loads(rr.SNAPSHOT.read_text()), flat=True)
    assert not problems, "\n".join(problems)


@needs_readme
@needs_metrics
def test_snapshot_is_current_with_metrics_json():
    want = rr.snapshot_from(json.loads(rr.METRICS.read_text()), None, rr.load_extra())
    assert json.loads(rr.SNAPSHOT.read_text()) == want, "stale: run scripts/readme_results.py --write-snapshot"


def test_lookup_indexes_lists_and_scales_percent_shares():
    ref = {"g": {"intervals": {"caught_share": {"estimate": 2 / 3, "ci95": [0.333, 1.0]}}, "sensitivity": [{"usd": 1}, {"usd": -10268.9}]}}
    text = "\n".join([
        "<!-- metrics-table[stats]: g. -->",
        "| metric | `x` | meaning |",
        "|---|---|---|",
        "| `intervals.caught_share.estimate@pct` | 66.7 | share |",
        "| `intervals.caught_share.ci95.0@pct` | 33.3 | lower |",
        "| `sensitivity.1.usd` | -10,269 | five bars |",
    ])
    assert rr.check(text, {}, extra={"stats": ref}) == []
    assert len(rr.check(text.replace("33.3", "34.3"), {}, extra={"stats": ref})) == 1
    assert len(rr.check(text.replace("sensitivity.1.usd", "sensitivity.5.usd"), {}, extra={"stats": ref})) == 1  # index out of range
    assert len(rr.check(text.replace("ci95.0@pct", "ci95.0"), {}, extra={"stats": ref})) == 1                  # 0.333 is not 33.3


@needs_readme
def test_readme_stats_tables_are_checked_against_docs_stats_results():
    """The statistics section's tables (against-chance p-values, intervals, five-bar fills) cite docs/stats/results.json."""
    assert "stats" in rr.EXTRA_SOURCES and rr.EXTRA_SOURCES["stats"].exists(), "docs/stats/results.json missing"
    cited_stats = [p for p in cited() if p.startswith("stats::")]
    assert len(cited_stats) >= 60, "the statistics tables are missing or were shortened"
    for group in ("sgx_august", "oos_round1", "oos_round2", "chips_new"):  # every dataset, round 2 included
        assert any(f"groups.{group}." in p for p in cited_stats), group
    for needle in ("chance.caught_storms.p_value", "chance.policy_difference_usd.holm_p_value",
                   "intervals.caught_share.ci95.0@pct", "sensitivity.5.policy.prepared_minus_unprepared_usd"):
        assert any(needle in p for p in cited_stats), needle
    problems = rr.check_all({}, extra={"stats": json.loads(rr.EXTRA_SOURCES["stats"].read_text())})
    problems = [m for m in problems if "stats::" in m]
    assert not problems, "\n".join(problems)


@needs_readme
def test_readme_round_2_tables_equal_results_2_json_and_state_the_prefix():
    """Round 2 (January to July 2025) is cited from docs/oos/results-2.json, and the README says it is a prefix."""
    assert rr.EXTRA_SOURCES["oos2"].exists(), "docs/oos/results-2.json missing"
    text = docs_text()
    cited_oos2 = [p for p in cited() if p.startswith("oos2::")]
    for needle in ("display.metrics.caught", "display.metrics.false_alarm_episodes_per_day",
                   "display.policy.helped", "display.policy.hurt", "display.policy.ties", "display.policy.total_difference_usd",
                   "display.policy.margin_calls_avoided"):
        assert any(p.endswith(needle) for p in cited_oos2), needle
    problems = rr.check_all({}, extra={"oos2": json.loads(rr.EXTRA_SOURCES["oos2"].read_text())})
    problems = [m for m in problems if "oos2::" in m]
    assert not problems, "\n".join(problems)
    results = json.loads(rr.EXTRA_SOURCES["oos2"].read_text())["display"]
    assert results["status"] == "chronological_prefix" and f"{results['usable_pair_months']} of {results['planned_pair_months']}" in text
    assert "not better than random timing" in text and "p=0.37" in text  # the unflattering reading stays in the README


def test_cells_marker_names_each_cell_and_skips_dashes():
    text = "\n".join([
        "<!-- metrics-cells",
        "a.storms | - | stats::g.p",
        "b.storms | b.caught | -",
        "-->",
        "| Dataset | Storms | Verdict or caught | p |",
        "|---|---|---|---|",
        "| **July** | 7 | in-sample | 0.0006 |",
        "| August | 6 | 4 | words |",
    ])
    cells = [(p, n) for p, _, _, n in rr.parse_tables(text)]
    assert cells == [("a.storms", 7.0), ("stats::g.p", 0.0006), ("b.storms", 6.0), ("b.caught", 4.0)]
    ref, extra = {"a": {"storms": 7}, "b": {"storms": 6, "caught": 4}}, {"stats": {"g": {"p": 0.00061}}}
    assert rr.check(text, ref, extra=extra) == []
    assert len(rr.check(text.replace("| 6 |", "| 5 |"), ref, extra=extra)) == 1
    with pytest.raises(ValueError):
        rr.parse_tables(text.replace("a.storms | - | stats::g.p", "a.storms | -"))   # a row of the wrong width
    with pytest.raises(ValueError):
        rr.parse_tables(text + "\n| September | 1 | 2 | 3 |")                      # more table rows than marker rows


@needs_readme
def test_readme_what_we_tested_table_covers_every_dataset_and_is_checked():
    """The compact table in the README: July (from evidence.json), August, rounds 1 and 2 and the chips."""
    text = README.read_text()
    assert "## What we tested" in text and "docs/results.md" in text
    readme_cells = [p for p, *_ in rr.parse_tables(text)]
    assert any(p.startswith("evidence::datasets.0.headline.") for p in readme_cells)
    for group in ("sgx_august", "oos_round1", "oos_round2", "chips_new"):
        assert any(p.startswith(f"stats::groups.{group}.chance.caught_storms.p_value") for p in readme_cells), group
    assert json.loads(rr.EXTRA_SOURCES["evidence"].read_text())["datasets"][0]["id"] == "sgx-july"
    assert rr.check(text, {}, extra=rr.load_extra()) == []
