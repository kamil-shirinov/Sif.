import json

import pytest

from storm.ai import inspector, llm, report
from storm.ai.verify import extract_numbers, verify_numbers


def test_verifier_rejects_invention_wrong_rounding_and_sign():
    facts = {"move_bp": -247.2, "equity_usd": 869137, "ratio": 12.345}
    assert verify_numbers("The move was -247 bp; equity was $869,137; ratio 12.35.", facts)["verified"]
    assert not verify_numbers("The move was -247.3 bp.", facts)["verified"]
    assert not verify_numbers("The move was 247.2 bp.", facts)["verified"]
    assert verify_numbers("Invented 999999.", facts)["unverified_numbers"] == ["999999"]
    assert not verify_numbers("Ratio 12.34.", facts)["verified"]


def test_verifier_checks_words_scales_percent_and_booleans():
    facts = {"count": 24, "notional": 20_000_000, "cut_pct": 75, "enabled": True}
    assert verify_numbers("Twenty-four positions, $20m, and 75%.", facts)["verified"]
    assert not verify_numbers("twenty-five positions", facts)["verified"]
    assert not verify_numbers("one position", facts)["verified"]
    assert extract_numbers("$1.25 million and −2.5%") == ["$1.25 million", "−2.5"]


def test_mock_report_and_facts(bundle):
    facts = report.facts_from_bundle(bundle)
    assert facts["storm"]["duration_minutes"] == 54
    assert facts["storm"]["move_pct"] == -2.472
    assert facts["ships"]["equity_saved_usd"] == 373273
    assert facts["ships"]["prepared"]["pnl_usd"] == -130863
    assert facts["alarm_events"][0]["minutes_from_onset"] == 1
    assert facts["ships"]["unprepared"]["margin_call"] is True
    assert facts["exposure"] == bundle["exposure"]
    assert facts["stress"] == bundle["stress"]
    result = report.write_report(facts)
    assert result["verified"] is True
    assert result["unverified_numbers"] == []
    assert result["inspector"]["verdict"] == "ok"
    assert result["cost_usd"] == 0
    assert result["model"] == "mock"
    assert "synthetic book" in result["text"]
    assert result["attempts"] == 1
    assert result["first_try_verified"]


def test_retry_lists_bad_numbers_then_falls_back(bundle, monkeypatch):
    original = llm.complete
    calls = []

    def invented(messages, **kwargs):
        if kwargs["purpose"] == "storm-report":
            calls.append(messages)
            return {"text": "The synthetic book lost $99999999. Alarm failed. Seas rose.",
                    "model": "test-writer", "cost_usd": .01}
        return original(messages, **kwargs)

    monkeypatch.setattr(llm, "complete", invented)
    result = report.write_report(report.facts_from_bundle(bundle))
    assert len(calls) == 2
    correction = json.loads(calls[1][-1]["content"])["correction"]
    assert correction["bad_numbers"] == ["$99999999"]
    assert result["model"] == "deterministic"
    assert result["verified"] and result["fallback"]
    assert not result["first_try_verified"]
    assert result["cost_usd"] == .02


def test_inspector_flags_unsupported_claim_and_report_replaces_it(bundle, monkeypatch):
    original = llm.complete

    def unsupported(messages, **kwargs):
        response = original(messages, **kwargs)
        if kwargs["purpose"] == "storm-report":
            response["text"] = "The synthetic book was safe. A surprise election caused the move. Prices will recover."
        return response

    monkeypatch.setattr(llm, "complete", unsupported)
    result = report.write_report(report.facts_from_bundle(bundle))
    assert result["first_try_verified"]  # numeric membership alone cannot catch this
    assert result["fallback"]
    assert result["inspector"]["initial_audit"]["verdict"] == "flag"
    assert result["inspector"]["verdict"] == "ok"
    assert "election" not in result["text"]


@pytest.mark.parametrize("raw", ['{}', '[]', '{"verdict":"ok","issues":["bad"]}', 'not json'])
def test_malformed_inspection_fails_closed(bundle, monkeypatch, raw):
    monkeypatch.setattr(llm, "complete", lambda *a, **k: {"text": raw, "model": "checker", "cost_usd": 0})
    assert inspector.inspect_report("text", report.facts_from_bundle(bundle))["verdict"] == "flag"


def test_inspector_requires_different_family(bundle, monkeypatch):
    monkeypatch.setenv("FIREWORKS_MODEL_CHECKER", "accounts/fireworks/models/muse-ember-1.0")
    with pytest.raises(llm.GatewayError, match="different model family"):
        inspector.inspect_report("text", report.facts_from_bundle(bundle), live=True)


def test_scheduled_watch_and_no_alarm(bundle):
    bundle["storm"]["kind"] = "scheduled"
    bundle["events"] = [{"type": "watch", "i": 200, "at_i": 210, "text": "Scheduled release"}]
    facts = report.facts_from_bundle(bundle)
    assert facts["alarm_events"][0]["minutes_before_release"] == 10
    result = report.write_report(facts)
    assert result["verified"]
    assert "No storm alarm" in result["text"]


def test_nullable_alarm_and_exposure_metrics(bundle):
    bundle["events"][0]["move_ahead_pct"] = None
    bundle["exposure"]["leverage"] = None
    bundle["exposure"]["margin_buffer_pct"] = None
    result = report.write_report(report.facts_from_bundle(bundle))
    assert result["verified"] and result["inspector"]["verdict"] == "ok"
    assert "stress scenario" in result["text"]
    assert "None" not in result["text"]


def test_report_preflights_inspector_before_spending(bundle, monkeypatch):
    monkeypatch.setenv("FIREWORKS_MODEL_CHECKER", "muse-spark-1.2")
    monkeypatch.setattr(llm, "complete", lambda *a, **k: pytest.fail("No inference before family validation"))
    with pytest.raises(llm.GatewayError, match="different model family"):
        report.write_report(report.facts_from_bundle(bundle), live=True)
