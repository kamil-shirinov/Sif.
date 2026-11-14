import json

import pytest

from storm.ai import llm, navigator, scenario, tools
from storm.ai.verify import verify_numbers


@pytest.fixture
def exported(bundle, tmp_path, monkeypatch):
    directory = tmp_path / 'bundles'
    directory.mkdir()
    (directory / 'fixture.json').write_text(json.dumps(bundle))
    monkeypatch.setattr(scenario, 'BUNDLES_DIR', directory)
    return directory


def test_mock_tool_round_trip_creates_verified_scenario(exported, monkeypatch):
    original = llm.complete
    calls = []

    def track(messages, **kwargs):
        calls.append((messages.copy(), kwargs))
        return original(messages, **kwargs)

    monkeypatch.setattr(llm, 'complete', track)
    result = navigator.ask('what if USDJPY drops 3% in 30 minutes?', 'fixture')
    assert result['verified'] and result['unverified_numbers'] == []
    assert result['inspector']['verdict'] == 'ok'
    assert result['scenario']['source'] == 'scenario'
    assert result['tool_calls'][0]['name'] == 'scenario'
    assert result['tool_calls'][0]['arguments']['move_pct'] == -3
    assert 'error' not in result['tool_calls'][0]['result']
    assert 'hypothetical' in result['answer'] and 'synthetic' in result['answer']
    assert len(calls) == 3  # Tool call, prose, independent inspector.
    assert calls[0][1]['provider'] == 'meta'
    assert calls[0][1]['tools'] == tools.TOOL_SCHEMAS
    assert calls[1][0][-1]['role'] == 'tool'
    assert calls[1][0][-1]['tool_call_id'] == result['tool_calls'][0]['id']
    assert 'series' not in calls[1][0][-1]['content']  # Compact facts, not a huge replay.
    facts = {'tool_results': [result['tool_calls'][0]['result']]}
    assert verify_numbers(result['answer'], facts, allow_direction_words=True)['verified']
    assert not verify_numbers(result['answer'] + ' Invented $987654321.', facts, allow_direction_words=True)['verified']


def test_invented_number_retries_once_then_uses_verified_template(exported, monkeypatch):
    original = llm.complete
    attempts = []

    def invent(messages, **kwargs):
        response = original(messages, **kwargs)
        if kwargs['purpose'] in {'storm-navigator', 'navigator-answer'} and not response['tool_calls']:
            attempts.append((messages, kwargs))
            response['text'] = 'The synthetic book lost $987654321. This is hypothetical.'
        return response

    monkeypatch.setattr(llm, 'complete', invent)
    result = navigator.ask('what if USDJPY drops 3% in 30 minutes?', 'fixture')
    assert len(attempts) == 2
    correction = json.loads(attempts[1][0][-1]['content'])['correction']
    assert correction['unverified_numbers'] == ['$987654321']
    assert result['verified'] and result['unverified_numbers'] == []
    assert '987654321' not in result['answer']
    assert result['inspector']['verdict'] == 'ok'


def test_inspector_flags_semantic_invention_and_audits_final_fallback(exported, monkeypatch):
    original = llm.complete

    def invent(messages, **kwargs):
        response = original(messages, **kwargs)
        if kwargs['purpose'] == 'storm-navigator' and not response['tool_calls']:
            response['text'] = 'The synthetic book is safe. An election caused the move.'
        return response

    monkeypatch.setattr(llm, 'complete', invent)
    result = navigator.ask('stress USDJPY down 3% in 30 minutes', 'fixture')
    assert result['verified']
    assert result['inspector']['initial_audit']['verdict'] == 'flag'
    assert result['inspector']['verdict'] == 'ok'
    assert 'election' not in result['answer']


@pytest.mark.parametrize('question,expected', [
    ('What is my exposure?', 'get_exposure'),
    ('List available storms', 'list_storms'),
    ('Stress USDJPY down 3% in 30 minutes', 'stress_test'),
])
def test_other_tools_are_grounded(exported, question, expected):
    result = navigator.ask(question, 'fixture')
    assert result['tool_calls'][0]['name'] == expected
    assert result['verified'] and result['inspector']['verdict'] == 'ok'
    assert result['scenario'] is None


def test_tool_errors_are_recorded_and_not_replaced_with_fake_numbers(exported):
    result = navigator.ask('what if USDJPY drops 3% in 30 minutes?', 'missing')
    assert 'error' in result['tool_calls'][0]['result']
    assert result['scenario'] is None
    assert 'could not complete' in result['answer']
    assert result['verified']


def test_arguments_are_not_allowed_to_justify_answer_numbers(exported, monkeypatch):
    original = llm.complete
    monkeypatch.setitem(tools.FUNCTIONS, 'stress_test', lambda **kwargs: {'error': 'Unavailable'})

    def invent(messages, **kwargs):
        response = original(messages, **kwargs)
        if kwargs['purpose'] == 'storm-navigator' and not response['tool_calls']:
            response['text'] = 'The synthetic book lost 3%. This is hypothetical.'
        return response

    monkeypatch.setattr(llm, 'complete', invent)
    result = navigator.ask('Stress USDJPY down 3% in 30 minutes', 'fixture')
    assert result['tool_calls'][0]['arguments']['move_pct'] == -3
    assert '3%' not in result['answer']
    assert result['verified']


def test_schemas_and_dispatch_reject_unregistered_calls():
    assert {item['function']['name'] for item in tools.TOOL_SCHEMAS} == set(tools.FUNCTIONS)
    with pytest.raises(ValueError, match='Unknown'):
        tools.execute('exec', {})
    with pytest.raises(ValueError, match='Unexpected'):
        tools.execute('scenario', {'base_bundle': {}})
    with pytest.raises(ValueError, match='Missing'):
        tools.execute('stress_test', {})
    with pytest.raises(ValueError, match='object'):
        tools.execute('scenario', [])


def test_live_configuration_preflight_happens_before_writer(exported, monkeypatch):
    monkeypatch.setenv('FIREWORKS_MODEL_CHECKER', 'muse-spark-1.1')
    monkeypatch.setattr(llm, 'complete', lambda *a, **k: pytest.fail('No inference before preflight'))
    with pytest.raises(llm.GatewayError, match='different model family'):
        navigator.ask('exposure?', 'fixture', live=True)


def test_cli_offline_writes_bundle(exported, tmp_path, capsys):
    directory = tmp_path / 'output'
    assert navigator.main(['what if USDJPY drops 3% in 30 minutes?', '--storm', 'fixture',
                           '--bundles', str(exported), '--out', str(directory)]) == 0
    output = capsys.readouterr().out
    result = json.loads(output[output.index('{'):])
    assert result['verified'] and result['inspector']['verdict'] == 'ok'
    files = list(directory.glob('scenario-*.json'))
    assert len(files) == 1
    assert json.loads(files[0].read_text()) == result['scenario']


@pytest.mark.parametrize("move,pnl,margin,phrase", [
    (-3, -618557, True, "A 3% fall over 30 minutes would cost this synthetic USDJPY book $618,557 and trigger a margin call."),
    (-3, 618557, False, "A 3% fall over 30 minutes would give this synthetic USDJPY book a gain of $618,557 without triggering a margin call."),
    (3, -618557, False, "A 3% rise over 30 minutes would cost this synthetic USDJPY book $618,557 without triggering a margin call."),
    (0, 0, False, "A 0% move over 30 minutes would leave this synthetic USDJPY book unchanged without triggering a margin call."),
])
def test_stress_prose_uses_direction_actual_pnl_and_margin(move, pnl, margin, phrase):
    facts = {"tool_results": [{"name": "stress_test", "result": {
        "symbol": "USDJPY", "move_pct": move, "minutes": 30,
        "pnl_usd": pnl, "margin_call": margin, "book_is_synthetic": True}}]}
    text = navigator.deterministic_answer(facts)
    assert text.startswith(phrase)
    assert "hypothetical" in text and "before liquidation" in text
    assert not navigator._format_issues(text)
    assert verify_numbers(text, facts, allow_direction_words=True)["verified"]


@pytest.mark.parametrize("text,verified", [
    ("A 3% fall over 30 minutes would cost this book $618,557.", True),
    ("A fall of 3% over 30 minutes would cause a loss of $618,557.", True),
    ("A three percent fall would lose $618,557.", True),
    ("A 3% rise over 30 minutes would cost this book $618,557.", False),
    ("A 3% fall over 30 minutes would give this book a gain of $618,557.", False),
    ("A 3% fall would cost this book $618,558.", False),
    ("The book is worth $618,557.", False),
    ("A -3% rise would gain $-618,557.", False),
    ("A 3% fall would cost this book $618,557. Invented $987654321.", False),
])
def test_directional_prose_still_checks_each_number_and_sign(text, verified):
    facts = {"move_pct": -3, "minutes": 30, "pnl_usd": -618557}
    assert verify_numbers(text, facts, allow_direction_words=True)["verified"] is verified


def test_direction_words_are_checked_by_default_and_literal_only_mode_remains():
    facts = {"move_pct": -3, "pnl_usd": -618557}
    text = "A 3% fall would cost this book $618,557."
    assert not verify_numbers(text, facts, allow_direction_words=False)["verified"]
    assert verify_numbers(text, facts)["verified"]


def test_navigator_rewrites_numeric_field_dump_in_plain_english(monkeypatch):
    original = llm.complete
    corrections = []

    def dump_fields(messages, **kwargs):
        response = original(messages, **kwargs)
        if kwargs["purpose"] == "storm-navigator" and not response["tool_calls"]:
            payload = json.loads(messages[-1]["content"])
            response["text"] = (f"For the synthetic book, move_pct {payload['move_pct']} in minutes "
                                f"{payload['minutes']} shows pnl_usd {payload['pnl_usd']}. "
                                "This is hypothetical.")
        if kwargs["purpose"] == "navigator-answer":
            corrections.append(json.loads(messages[-1]["content"])["correction"])
            assert "plain English" in messages[0]["content"]
        return response

    monkeypatch.setattr(llm, "complete", dump_fields)
    result = navigator.ask("Stress USDJPY down 3% in 30 minutes")
    assert result["verified"] and result["inspector"]["verdict"] == "ok"
    assert len(corrections) == 1
    assert "Translate raw field names into plain English for a trader" in corrections[0]["issues"]
    assert "move_pct" not in result["answer"] and "pnl_usd" not in result["answer"]
    assert "3% fall over 30 minutes" in result["answer"] and "would cost" in result["answer"]
