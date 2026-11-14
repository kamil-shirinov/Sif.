"""Live API over Tiger Data, per contracts/api.md.

    cd backend && ~/.venvs/stormscore/bin/python -m uvicorn storm.live.api:app --port 8000

The web app reaches it through the Vite proxy at /api and must work without it, so every
failure here is a clean HTTP status, never a hang.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..features import PAIRS
from . import sql
from .db import SharedConnection, TigerConfigError, scrub

MAX_CANDLE_RANGE = timedelta(days=14)
STATS_TTL_S = 60.0

try:
    from ..ai.navigator_api import router as navigator_router
except Exception:  # the navigator is optional; /api/health reports it as false
    navigator_router = None

db = SharedConnection()
_stats_cache: dict = {"at": 0.0, "value": None}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    db.close()


app = FastAPI(title="StormScore live API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
if navigator_router is not None:
    app.include_router(navigator_router)


class Health(BaseModel):
    ok: bool
    tiger: bool
    navigator: bool


class Rows(BaseModel):
    spot_1m: int
    forward_1m: int


class Stats(BaseModel):
    rows: Rows
    bytes_before: int
    bytes_after: int
    compression_ratio: float
    continuous_aggregates: list[str]


class Storm(BaseModel):
    storm_id: str
    symbol: str
    onset: str
    move_bp: float
    kind: str
    event: str | None


class Candle(BaseModel):
    t: int
    open: float
    high: float
    low: float
    close: float


class Candles(BaseModel):
    bucket: str
    query_ms: float
    candles: list[Candle]


def parse_time(value: str, name: str) -> datetime:
    """ISO 8601 -> aware UTC datetime. A trailing Z and a naive time are both read as UTC."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"'{name}' is not an ISO 8601 time") from None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def iso_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def candle_rows(rows: list[tuple]) -> list[dict]:
    return [{"t": int(t), "open": o, "high": h, "low": lo, "close": c} for t, o, h, lo, c in rows]


def storm_rows(rows: list[tuple]) -> list[dict]:
    return [
        {"storm_id": sid, "symbol": sym, "onset": iso_utc(onset), "move_bp": move, "kind": kind, "event": event or None}
        for sid, sym, onset, move, kind, event in rows
    ]


def stats_payload(counts: dict[str, int], sizes: tuple[int, int], aggregates: list[str]) -> dict:
    before, after = sizes
    return {
        "rows": counts,
        "bytes_before": before,
        "bytes_after": after,
        "compression_ratio": round(before / after, 2) if after else 0.0,
        "continuous_aggregates": aggregates,
    }


def _query(statement: str, params: tuple | None = None) -> list[tuple]:
    try:
        return db.fetch(statement, params)
    except (psycopg.Error, TigerConfigError) as error:
        print(f"tiger query failed ({type(error).__name__}): {scrub(error)[:200]}")
        raise HTTPException(status_code=503, detail="Tiger Data is unavailable") from None


@app.get("/api/health", response_model=Health)
def health() -> dict:
    try:
        tiger = bool(db.fetch("SELECT 1"))
    except (psycopg.Error, TigerConfigError):
        tiger = False
    return {"ok": True, "tiger": tiger, "navigator": navigator_router is not None}


@app.get("/api/stats", response_model=Stats)
def stats() -> dict:
    now = time.monotonic()
    if _stats_cache["value"] is not None and now - _stats_cache["at"] < STATS_TTL_S:
        return _stats_cache["value"]
    counts = {t: int(_query(sql.count_statement(t))[0][0]) for t in sql.HYPERTABLES}
    before, after = _query(sql.COMPRESSION_STATS_QUERY)[0]
    aggregates = [name for (name,) in _query(sql.AGGREGATES_QUERY)]
    value = stats_payload(counts, (int(before), int(after)), aggregates)
    _stats_cache.update(at=now, value=value)
    return value


@app.get("/api/storms", response_model=list[Storm])
def storms() -> list[dict]:
    return storm_rows(_query(sql.STORMS_QUERY))


@app.get("/api/candles", response_model=Candles)
def candles(
    symbol: str = Query(...),
    start: str = Query(..., alias="from"),
    end: str = Query(..., alias="to"),
) -> dict:
    symbol = symbol.upper()
    if symbol not in PAIRS:
        raise HTTPException(status_code=422, detail=f"symbol must be one of {', '.join(PAIRS)}")
    t0, t1 = parse_time(start, "from"), parse_time(end, "to")
    if t1 <= t0:
        raise HTTPException(status_code=422, detail="'to' must be after 'from'")
    if t1 - t0 > MAX_CANDLE_RANGE:
        raise HTTPException(status_code=422, detail=f"range is limited to {MAX_CANDLE_RANGE.days} days")
    began = time.perf_counter()
    rows = _query(sql.CANDLES_QUERY, (symbol, t0, t1))
    query_ms = (time.perf_counter() - began) * 1000
    return {"bucket": sql.CANDLE_BUCKET_LABEL, "query_ms": round(query_ms, 2), "candles": candle_rows(rows)}
