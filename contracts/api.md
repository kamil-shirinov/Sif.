# Live API (backend/storm/live/api.py, http://localhost:8000; the web app reaches it via the Vite proxy at /api and must work without it)
GET /api/health -> {"ok": true, "tiger": bool, "navigator": bool}
GET /api/stats -> {"rows": {"spot_1m": int, "forward_1m": int}, "bytes_before": int, "bytes_after": int, "compression_ratio": float, "continuous_aggregates": [str]}
GET /api/storms -> [{"storm_id", "symbol", "onset", "move_bp", "kind", "event"}]
GET /api/candles?symbol=USDJPY&from=ISO8601&to=ISO8601 -> {"bucket": "5m", "query_ms": float, "candles": [{"t": epoch_s, "open", "high", "low", "close"}]}
POST /api/navigator/ask {"question": str, "storm_id": str or null} -> {"answer", "verified", "unverified_numbers", "tool_calls", "inspector", "scenario": bundle or null}
