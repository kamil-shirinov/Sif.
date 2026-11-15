import math

import pytest

from storm.ai import budget, llm, navigator, report, scenario
from storm.ai.navigator_bakeoff import cases, correct_tools


def test_task_ceiling_is_additional_and_does_not_count_other_tasks(caps, monkeypatch, capsys):
    monkeypatch.setenv('STORM_TASK_ID', 'models-test')
    monkeypatch.setenv('STORM_TASK_LIMITS_JSON', '{"meta":0.4}')
    call = budget.reserve('meta', 'unknown', 0, 20_000, 'test')
    assert '75%' in capsys.readouterr().err
    assert budget.task_spent('meta', 'models-test') == pytest.approx(.3)
    with pytest.raises(budget.BudgetExceeded, match='task'):
        budget.reserve('meta', 'unknown', 0, 4000, 'test')
    assert budget.task_spent('meta', 'other') == 0
    budget.failed(call, definitely_unbilled=True)
    assert budget.task_spent('meta', 'models-test') == 0


def test_task_configuration_fails_closed(caps, monkeypatch):
    monkeypatch.setenv('STORM_TASK_ID', 'models-test')
    with pytest.raises(budget.BudgetError):
        budget.reserve('meta', 'unknown', 1, 1, 'test')
    monkeypatch.setenv('STORM_TASK_LIMITS_JSON', '{"meta":NaN}')
    with pytest.raises(budget.BudgetError):
        budget.reserve('meta', 'unknown', 1, 1, 'test')


def test_leverage_scales_endpoint_pnl_and_preserves_default():
    low = scenario.stress_test('USDJPY', -2, 30, leverage=10)
    high = scenario.stress_test('USDJPY', -2, 30, leverage=40)
    assert high['notional_usd'] == 4 * low['notional_usd']
    assert high['pnl_usd'] == pytest.approx(4 * low['pnl_usd'], abs=2)
    assert low['leverage'] == 10 and high['leverage'] == 40
    assert scenario.stress_test('USDJPY', -2, 5)['pnl_usd'] == scenario.stress_test('USDJPY', -2, 120)['pnl_usd']


@pytest.mark.parametrize('leverage', [True, 0, -1, math.inf, math.nan, 1001])
def test_invalid_leverage_rejected(leverage):
    with pytest.raises(ValueError, match='leverage'):
        scenario.stress_test('USDJPY', -2, 30, leverage=leverage)


def test_fixed_ten_cases_and_tool_scoring_reject_wrong_sign_or_missing_step():
    assert len(cases()) == len({c[0] for c in cases()}) == 10
    expected = cases()[6][3]
    actual = [{**c, 'result': {}} for c in expected]
    assert correct_tools(actual, expected)
    assert not correct_tools(actual[:1], expected)
    actual[0] = {**actual[0], 'arguments': {**actual[0]['arguments'], 'move_pct': 2}}
    assert not correct_tools(actual, expected)


def test_report_default_uses_measured_winner_and_keeps_explicit_meta_route(bundle, monkeypatch):
    complete = llm.complete
    seen = []

    def track(*args, **kwargs):
        if kwargs['purpose'] == 'storm-report':
            seen.append((kwargs['provider'], kwargs['model']))
        return complete(*args, **kwargs)

    monkeypatch.setattr(llm, 'complete', track)
    facts = report.facts_from_bundle(bundle)
    report.write_report(facts)
    report.write_report(facts, model='muse-spark-1.3')
    assert seen == [('fireworks', 'accounts/fireworks/models/glm-5p3'), ('meta', 'muse-spark-1.3')]
