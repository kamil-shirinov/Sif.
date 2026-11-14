"""Readable reports must retain source numbers, clock instants and direction."""

from copy import deepcopy
import json
import re

import pytest

from storm.ai import llm, report
from storm.ai.presentation import format_utc, money, report_sentences
from storm.ai.verify import verify_numbers


@pytest.mark.parametrize("source,expected", [
    ("2026-11-11T21:57:00Z", "11 Nov, 21:57 UTC"),
    ("2026-11-12T00:57:00+03:00", "11 Nov, 21:57 UTC"),
    ("2026-07-01T00:01:05Z", "1 Jul, 00:01:05 UTC"),
])
def test_utc_presentation_and_verification_use_the_same_instant(source, expected):
    assert format_utc(source) == expected
    assert verify_numbers(f"The alarm sounded at {expected}.", {"alarm_utc": source})["verified"]


@pytest.mark.parametrize("invented", [
    "12 Nov, 21:57 UTC", "11 Dec, 21:57 UTC", "11 Nov, 22:57 UTC",
    "11 Nov, 21:58 UTC", "11 Nov, 21:57:01 UTC", "31 Feb, 21:57 UTC",
])
def test_invented_human_timestamps_fail_even_if_each_number_exists(invented):
    facts = {"alarm_utc": "2026-11-11T21:57:00Z", "other_utc": "2026-11-12T22:58:01Z",
             "unrelated_numbers": [1, 11, 12, 21, 22, 31, 57, 58]}
    result = verify_numbers(f"The alarm sounded at {invented}.", facts)
    assert result == {"verified": False, "unverified_numbers": [invented]}


def test_malformed_source_timestamp_is_not_an_allowed_human_date():
    assert not verify_numbers("At 11 Nov, 21:57 UTC.", {"time": "2026-99-99T21:57:00Z"})["verified"]


def test_writer_receives_only_formatted_statements_and_inspector_keeps_source_facts(bundle, monkeypatch):
    facts = report.facts_from_bundle(bundle)
    before = deepcopy(facts)
    complete = llm.complete
    requests = []

    def capture(messages, **kwargs):
        requests.append((kwargs["purpose"], json.loads(messages[-1]["content"])))
        return complete(messages, **kwargs)

    monkeypatch.setattr(llm, "complete", capture)
    result = report.write_report(facts)
    writer = requests[0][1]["facts"]
    assert writer == {"report_sentences": report_sentences(facts)}
    assert not re.search(r"\d{4}-\d{2}-\d{2}T", json.dumps(writer))
    assert "onset_utc" not in json.dumps(writer) and "move_ahead_pct" not in json.dumps(writer)
    assert requests[-1][0] == "storm-inspector" and requests[-1][1]["facts"] == facts
    assert facts == before
    assert result["text"] == report.deterministic_report(facts)
    assert result["verified"] and result["inspector"]["verdict"] == "ok"
    assert "of the eventual move was still to come" in result["text"]
    assert not report._format_issues(result["text"])


def test_equity_duration_and_market_hours_note_are_not_repeated(bundle):
    facts = report.facts_from_bundle(bundle)
    facts["storm"].update(symbol="NVDA", duration_minutes=572,
                          onset_utc="2026-11-11T21:57:00Z", trough_utc="2026-11-12T23:29:00Z",
                          market_hours={"trading_minutes": 572, "clock_minutes": 1532,
                                        "closed_minutes": 960,
                                        "note": "duration_minutes is 572 trading minutes; 572 trading minutes again"})
    facts["alarm_events"] = [{"type": "alarm", "time_utc": "2026-11-11T22:05:00Z",
                               "minutes_from_onset": 8, "move_ahead_pct": 82.6}]
    result = report.write_report(facts)
    text = result["text"]
    assert text.count("572 trading minutes") == 1
    assert "11 Nov, 21:57 UTC" in text and "12 Nov, 23:29 UTC" in text
    assert "82.6% of the eventual move was still to come" in text
    assert "market closed between sessions" in text
    assert "duration_minutes" not in text and "move ahead" not in text
    assert result["verified"] and not report._format_issues(text)


@pytest.mark.parametrize("bad", [
    "The synthetic book was unchanged at 2026-11-11T21:57:00Z. No alarm sounded. Exposure was small.",
    "The synthetic book recorded move_pct -3. The alarm sounded. Exposure was small.",
    "The synthetic book changed with 82.6% move ahead. The alarm sounded. Exposure was small.",
    "The synthetic book fell over 572 trading minutes. It moved for 572 trading minutes. No alarm sounded.",
    "The synthetic book fell over 54 minutes. The move lasted 54 minutes. No alarm sounded.",
    "The synthetic book was unchanged. No alarm sounded. No alarm sounded.",
    "The synthetic book was unchanged at 21:57 UTC. No alarm sounded. Exposure was small.",
])
def test_raw_fields_iso_clocks_and_repeated_facts_fail_the_style_check(bad):
    assert report._format_issues(bad)


@pytest.mark.parametrize("text,expected", [
    ("USDJPY fell 247.2 basis points.", True),
    ("USDJPY recorded a 247.2 basis point fall.", True),
    ("USDJPY rose 247.2 basis points.", False),
    ("USDJPY recorded a 247.2 basis point rise.", False),
    ("The alarm sounded 8 minutes before the move began.", True),
    ("The alarm sounded 8 minutes after the move began.", False),
    ("The prepared ship finished $1,000 behind.", True),
    ("The prepared ship finished $1,000 ahead.", False),
    ("USDJPY fell 248 basis points.", False),
])
def test_formatted_move_timing_and_equity_keep_the_economic_sign(text, expected):
    facts = {"move_bp": -247.2, "minutes_from_onset": -8, "equity_saved_usd": -1000}
    assert verify_numbers(text, facts, allow_direction_words=True)["verified"] is expected


def test_equal_ships_and_negative_gap_have_readable_verified_fallbacks(bundle):
    facts = report.facts_from_bundle(bundle)
    for name in ("prepared", "unprepared"):
        facts["ships"][name]["final_equity_usd"] = 1000000
    facts["ships"]["equity_saved_usd"] = 0
    text = report.deterministic_report(facts)
    assert text.count("$1,000,000") == 1 and "Both ships" in text
    assert verify_numbers(text, facts, allow_direction_words=True)["verified"]
    facts["ships"]["prepared"]["final_equity_usd"] = 999000
    facts["ships"]["equity_saved_usd"] = -1000
    text = report.deterministic_report(facts)
    assert "$1,000 behind" in text
    assert verify_numbers(text, facts, allow_direction_words=True)["verified"]
    assert money(-1000) == "-$1,000"
