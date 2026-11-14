import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from storm.ai import navigator, scenario
from storm.ai.navigator_api import router


@pytest.fixture
def client(bundle, tmp_path, monkeypatch):
    (tmp_path / 'fixture.json').write_text(json.dumps(bundle))
    monkeypatch.setattr(scenario, 'BUNDLES_DIR', tmp_path)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        yield client


def test_router_shape_and_scenario(client):
    response = client.post('/api/navigator/ask', json={
        'question': 'what if USDJPY drops 3% in 30 minutes?', 'storm_id': 'fixture'})
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {'answer', 'verified', 'unverified_numbers', 'tool_calls', 'inspector', 'scenario'}
    assert isinstance(data['answer'], str)
    assert data['verified'] is True
    assert data['unverified_numbers'] == []
    assert isinstance(data['tool_calls'], list) and data['tool_calls']
    assert data['inspector']['verdict'] == 'ok'
    assert data['scenario']['source'] == 'scenario'


def test_router_optional_storm_and_null_scenario(client):
    response = client.post('/api/navigator/ask', json={'question': 'List storms'})
    assert response.status_code == 200
    assert response.json()['scenario'] is None


@pytest.mark.parametrize('payload', [{}, {'question': ''}, {'question': '   '},
    {'question': 'x' * 4001}, {'question': 'exposure', 'storm_id': '../../outside'}])
def test_router_rejects_bad_requests(client, payload):
    assert client.post('/api/navigator/ask', json=payload).status_code == 422


def test_router_sanitizes_provider_errors(client, monkeypatch):
    from storm.ai.llm import GatewayError

    def fail(*args, **kwargs):
        raise GatewayError('private provider detail')

    monkeypatch.setattr(navigator, 'ask', fail)
    response = client.post('/api/navigator/ask', json={'question': 'exposure?'})
    assert response.status_code == 502
    assert 'private provider detail' not in response.text


def test_router_reports_missing_or_exhausted_budget(client, monkeypatch):
    from storm.ai.budget import BudgetError

    def fail(*args, **kwargs):
        raise BudgetError('private cap configuration')

    monkeypatch.setattr(navigator, 'ask', fail)
    response = client.post('/api/navigator/ask', json={'question': 'exposure?'})
    assert response.status_code == 503
    assert 'private cap configuration' not in response.text
