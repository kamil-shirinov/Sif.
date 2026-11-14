from copy import deepcopy

import numpy as np
import pytest

from storm import exposure
from storm.ai import scenario as module
from storm.validate import validate_bundle


@pytest.mark.parametrize('move,minutes', [(-3, 30), (-1.25, 1), (4.5, 91), (0, 60), (-.001, 7), (-3, 1440)])
def test_resized_path_has_requested_move_and_validates(bundle, move, minutes):
    original = deepcopy(bundle)
    result = module.scenario('USDJPY', move, minutes, base_bundle=bundle)
    assert result['source'] == 'scenario'
    assert result['n'] == minutes + 1
    assert result['storm']['trough_i'] - result['storm']['onset_i'] == minutes
    actual_bp = (result['series']['mid'][-1] / result['series']['mid'][0] - 1) * 10_000
    assert abs(actual_bp - move * 100) <= 1
    validation_copy = deepcopy(result)
    validation_copy['source'] = 'synthetic'  # CC-L adds the scenario enum separately.
    assert validate_bundle(validation_copy) == []
    assert result['source'] == 'scenario'
    assert bundle == original
    assert result['report'] is None
    assert 'synthetic replay' in result['title']
    assert '30 July' not in result['title']


def test_log_return_shape_and_equity_come_from_existing_simulator(bundle):
    onset, trough = bundle['storm']['onset_i'], bundle['storm']['trough_i']
    duration = trough - onset
    result = module.scenario('USDJPY', -3, duration, base_bundle=bundle)
    old = np.asarray(bundle['series']['mid'][onset:trough + 1])
    log_path = np.log(old / old[0])
    expected = old[0] * np.exp(log_path * np.log(.97) / log_path[-1])
    assert result['series']['mid'] == pytest.approx(expected, abs=5.1e-6)
    book, mids, paths = module.book_paths(result)
    direct = exposure.ships(mids, book, [(result['ships']['prepared']['cut_i'], 'USDJPY', 'cut')])
    for name, path in paths.items():
        assert result['series'][f'{name}_equity'] == [round(float(x)) for x in path.equity]
        assert result['ships'][name]['margin_call_i'] == path.margin_call_i
        assert path.equity == pytest.approx(direct[name].equity)
    assert result['ships']['prepared']['cut_i'] is not None
    assert result['ships']['unprepared']['margin_call_i'] is not None
    assert result['series']['prepared_equity'][-1] > result['series']['unprepared_equity'][-1]


def test_real_source_gets_real_shape_title(bundle):
    # Only title/provenance branching is tested here; prices remain a test fixture.
    bundle['source'] = 'sgx'
    bundle['t0'] = 1785369600  # 30 July 2026 UTC, before the fixture onset.
    result = module.scenario('USDJPY', -3, 30, base_bundle=bundle)
    assert 'shaped like 30 July' in result['title']


@pytest.mark.parametrize('symbol,move,minutes', [
    ('GBPUSD', -3, 30), ('USDJPY', -100, 30), ('USDJPY', float('nan'), 30),
    ('USDJPY', float('inf'), 30), ('USDJPY', True, 30), ('USDJPY', -3, 0),
    ('USDJPY', -3, 1.5), ('USDJPY', -3, True), ('USDJPY', -3, 1441),
])
def test_bad_parameters_are_rejected(bundle, symbol, move, minutes):
    with pytest.raises(ValueError):
        module.scenario(symbol, move, minutes, base_bundle=bundle)


def test_missing_real_bundle_is_never_silently_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'BUNDLES_DIR', tmp_path)
    with pytest.raises(FileNotFoundError, match='export'):
        module.scenario()
    with pytest.raises(ValueError, match='Invalid storm_id'):
        module.load_bundle('../../contracts/mock_storm')


def test_unusable_shape_and_mismatched_symbol_are_rejected(bundle):
    with pytest.raises(ValueError, match='match'):
        module.scenario('EURUSD', -3, 30, base_bundle=bundle)
    bundle['series']['mid'] = [100.] * bundle['n']
    with pytest.raises(ValueError, match='zero'):
        module.scenario(base_bundle=bundle)


@pytest.mark.parametrize('symbol,move,expected', [
    ('USDJPY', -3, 20e6 * (1 - 1 / .97)),
    ('EURUSD', 3, -600_000),
    ('USDSGD', -1, 20e6 * (1 - 1 / .99)),
])
def test_endpoint_stress_signs(symbol, move, expected):
    result = module.stress_test(symbol, move, 30)
    assert result['pnl_usd'] == round(expected)
    assert result['book_is_synthetic']
    assert result['margin_call'] == (1e6 + expected < .025 * 20e6)


def test_base_id_cannot_escape_output_directory(bundle):
    bundle['storm_id'] = '../../outside'
    with pytest.raises(ValueError, match='filename'):
        module.scenario(base_bundle=bundle)


def test_source_compatibility_keeps_other_validation_and_does_not_mutate(bundle):
    result = module.scenario(base_bundle=bundle)
    result['series']['risk'][0] = 2.0
    assert any('series.risk' in error for error in module.validate_shape(result))
    assert result['source'] == 'scenario'
    result['source'] = 'invented'
    assert any('source' in error for error in module.validate_shape(result))
