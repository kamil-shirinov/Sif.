"""Read-only checks against the real Tiger database. Needs .env with TIGER_DATABASE_URL and a
database already loaded with `python -m storm.live.tiger --load`; otherwise skipped."""
import pytest

from storm.live import sql
from storm.live.db import SharedConnection, env_file_has_url

pytestmark = pytest.mark.skipif(not env_file_has_url(), reason="no .env with TIGER_DATABASE_URL")


def test_loaded_database_serves_the_contract(real_network):
    conn = SharedConnection(timeout=15)
    try:
        if not conn.fetch(sql.TABLES_EXIST_QUERY)[0][0]:
            pytest.skip("Tiger is empty: run `python -m storm.live.tiger --load` first")
        from fastapi.testclient import TestClient
        from storm.live import api

        api.db = conn
        api._stats_cache["value"] = None
        with TestClient(api.app) as client:
            assert client.get("/api/health").json()["tiger"] is True
            stats = client.get("/api/stats").json()
            assert stats["rows"]["spot_1m"] > 100_000 and stats["bytes_after"] < stats["bytes_before"]
            assert {"candles_5m", "vol_1h"} <= set(stats["continuous_aggregates"])
            assert len(client.get("/api/storms").json()) >= 10
            body = client.get("/api/candles", params={
                "symbol": "USDJPY", "from": "2026-07-30T13:00:00Z", "to": "2026-07-30T15:00:00Z"}).json()
            assert len(body["candles"]) == 24 and body["query_ms"] > 0
            c = body["candles"][0]
            assert c["low"] <= min(c["open"], c["close"]) <= max(c["open"], c["close"]) <= c["high"]
    finally:
        conn.close()
