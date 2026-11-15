"""Published Markdown, null arrays and statistical denominators must agree with JSON."""
import copy
import json

import numpy as np
import pytest

from storm.stats.protocol import DOCS, registration, round2_cutoff
from storm.stats.randomization import null_summary, holm
from storm.stats.report import render, judge_sentences


def artifact():
    return json.loads((DOCS / "results.json").read_text())


def test_markdown_matches_json_and_judge_text_has_five_to_eight_sentences():
    result = artifact()
    assert (DOCS / "results.md").read_text() == render(result)
    assert 5 <= len(judge_sentences(result)) <= 8
    assert result["config"] == registration()["config"]
    assert result["provenance"]["effective_round2_cutoff_utc"] == round2_cutoff()
    assert "data/" not in result["units"][0]


def test_full_null_arrays_reproduce_pvalues_and_holm_family():
    result = artifact()
    tests, recorded = [], []
    for name, group in result["groups"].items():
        data = json.loads((DOCS / "nulls" / (name + ".json")).read_text())
        for statistic, values_key in (("caught_storms", "caught_counts"), ("policy_difference_usd", "policy_difference_usd")):
            if statistic not in group["chance"]:
                continue
            test = group["chance"][statistic]
            values = data[values_key]
            assert len(values) == (10000 if statistic == "caught_storms" else 1000)
            expected = null_summary(test["statistic"], values, test["fully_degenerate"])
            for key, value in expected.items():
                assert test[key] == value
            if not name.startswith("pooled"):
                tests.append(expected)
                recorded.append(test)
    holm(tests)
    for a, b in zip(tests, recorded):
        assert a["holm_p_value"] == b["holm_p_value"]


def test_counts_intervals_sensitivity_and_denominators_are_consistent():
    result = artifact()
    spec = registration()
    for name, group in result["groups"].items():
        p = group["point"]
        assert 0 <= p["caught"] <= p["alarmed"] <= p["storms"]
        if p["storms"]:
            assert p["caught_share"] == p["caught"] / p["storms"]
            assert p["alarmed_share"] == p["alarmed"] / p["storms"]
        assert p["false_alert_episodes_per_observed_day"] == pytest.approx(p["false_episodes"] / p["observed_days"])
        for key, row in group["intervals"].items():
            if key == "date_block":
                continue
            assert row["replicates"] == 10000
            lo, hi = row["ci95"]
            assert (lo is None and hi is None) or lo <= hi
        assert len(group["sensitivity"]) == sum(map(len, spec["sensitivity"].values()))
        for factor, values in spec["sensitivity"].items():
            assert [r["value"] for r in group["sensitivity"] if r["factor"] == factor] == values
        invalid = next(r for r in group["sensitivity"] if r["factor"] == "storm_on" and r["value"] == .7)
        assert invalid["status"] == "invalid"
    chips = result["groups"]["chips_new"]["point"]
    assert chips["false_alert_episodes_per_trading_day"] == chips["false_episodes"] / chips["trading_days"]
    assert all(c["passed"] for c in result["oracle_checks"])
