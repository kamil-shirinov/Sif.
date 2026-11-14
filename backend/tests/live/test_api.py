import psycopg
import pytest
from fastapi.testclient import TestClient

from storm.live import api

ONSET = __import__("datetime").datetime(2026, 7, 30, 13, 29, tzinfo=__import__("datetime").timezone.utc)


class FakeDb:
    def __init__(self, answers=None, error=None):
        self.answers, self.error, self.calls = answers or {}, error, []

    def fetch(self, statement, params=None):
        self.calls.append((statement, params))
        if self.error:
            raise self.error
        for needle, rows in self.answers.items():
            if needle in statement:
                return rows
        return []

    def close(self):
        pass


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(api._stats_cache, "value", None)
    with TestClient(api.app) as c:
        yield c


def use_db(monkeypatch, **kwargs):
    fake = FakeDb(**kwargs)
    monkeypatch.setattr(api, "db", fake)
    return fake


def test_health_shape_with_and_without_tiger(client, monkeypatch):
    use_db(monkeypatch, answers={"SELECT 1": [(1,)]})
    assert client.get("/api/health").json() == {"ok": True, "tiger": True, "navigator": True}
    use_db(monkeypatch, error=psycopg.OperationalError("down"))
    assert client.get("/api/health").json() == {"ok": True, "tiger": False, "navigator": True}


def test_navigator_route_comes_from_the_navigator_router(client):
    assert "/api/navigator/ask" in client.get("/openapi.json").json()["paths"]


def test_stats_shape_and_cache(client, monkeypatch):
    fake = use_db(monkeypatch, answers={
        "FROM spot_1m": [(193049,)], "FROM forward_1m": [(1661187,)],
        "hypertable_compression_stats": [(315_867_136, 42_950_656)],
        "continuous_aggregates": [("candles_5m",), ("vol_1h",)],
    })
    body = client.get("/api/stats").json()
    assert body == {
        "rows": {"spot_1m": 193049, "forward_1m": 1661187},
        "bytes_before": 315_867_136, "bytes_after": 42_950_656, "compression_ratio": 7.35,
        "continuous_aggregates": ["candles_5m", "vol_1h"],
    }
    calls = len(fake.calls)
    assert client.get("/api/stats").json() == body and len(fake.calls) == calls   # served from cache


def test_storms_shape(client, monkeypatch):
    use_db(monkeypatch, answers={"FROM storms": [
        ("usdjpy-2026-07-30", "USDJPY", ONSET, -290.36, "unscheduled", None),
        ("usdjpy-2026-07-02", "USDJPY", ONSET, -58.4, "scheduled", "US Employment Situation (June 2026)"),
    ]})
    storms = client.get("/api/storms").json()
    assert storms[0] == {"storm_id": "usdjpy-2026-07-30", "symbol": "USDJPY", "onset": "2026-07-30T13:29:00Z",
                         "move_bp": -290.36, "kind": "unscheduled", "event": None}
    assert storms[1]["event"] == "US Employment Situation (June 2026)"
    assert set(storms[0]) == {"storm_id", "symbol", "onset", "move_bp", "kind", "event"}


def test_candles_shape_and_bound_parameters(client, monkeypatch):
    fake = use_db(monkeypatch, answers={"FROM candles_5m": [(1785416400, 162.948, 162.961, 162.9085, 162.9485)]})
    r = client.get("/api/candles", params={"symbol": "usdjpy", "from": "2026-07-30T13:00:00Z", "to": "2026-07-30T15:00:00Z"})
    body = r.json()
    assert r.status_code == 200 and body["bucket"] == "5m" and isinstance(body["query_ms"], float)
    assert body["candles"] == [{"t": 1785416400, "open": 162.948, "high": 162.961, "low": 162.9085, "close": 162.9485}]
    _, params = fake.calls[-1]
    assert params[0] == "USDJPY" and params[1].isoformat() == "2026-07-30T13:00:00+00:00"
    assert params[2].isoformat() == "2026-07-30T15:00:00+00:00"


@pytest.mark.parametrize("query, status", [
    ({"symbol": "GBPUSD", "from": "2026-07-30T13:00:00Z", "to": "2026-07-30T15:00:00Z"}, 422),
    ({"symbol": "USDJPY", "from": "yesterday", "to": "2026-07-30T15:00:00Z"}, 422),
    ({"symbol": "USDJPY", "from": "2026-07-30T15:00:00Z", "to": "2026-07-30T13:00:00Z"}, 422),
    ({"symbol": "USDJPY", "from": "2026-07-01T00:00:00Z", "to": "2026-08-30T00:00:00Z"}, 422),
    ({"symbol": "USDJPY", "from": "2026-07-30T13:00:00Z"}, 422),
])
def test_candles_rejects_bad_input_without_touching_the_database(client, monkeypatch, query, status):
    fake = use_db(monkeypatch)
    assert client.get("/api/candles", params=query).status_code == status
    assert fake.calls == []


def test_naive_times_are_read_as_utc():
    assert api.parse_time("2026-07-30T13:00:00", "from").isoformat() == "2026-07-30T13:00:00+00:00"
    assert api.parse_time("2026-07-30T15:00:00+02:00", "from").isoformat() == "2026-07-30T13:00:00+00:00"


def test_database_failure_is_a_503_that_leaks_nothing(client, monkeypatch):
    use_db(monkeypatch, error=psycopg.OperationalError("could not connect to postgres://user:secret@host/db"))
    r = client.get("/api/storms")
    assert r.status_code == 503 and "secret" not in r.text and "postgres" not in r.text


def test_cors_allows_the_vite_origin_only(client, monkeypatch):
    use_db(monkeypatch, answers={"SELECT 1": [(1,)]})
    ok = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    other = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in other.headers
