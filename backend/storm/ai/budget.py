"""Atomic reservations keep simultaneous processes inside the provider cap.

Never change caps here. Pending calls (including interrupted processes) continue
to hold their full reservation; uncertain failures are conservatively charged.
Only token counts, model IDs, purpose labels and costs go into the ledger.
"""

from contextlib import contextmanager
from decimal import Decimal
import json
import math
from pathlib import Path
import sqlite3
import sys
import time
import uuid

from .prices import cost_usd

LEDGER_BUSY_TIMEOUT_MS = 30_000


def _is_locked(error: sqlite3.OperationalError) -> bool:
    # sqlite_errorcode and the symbolic constants appeared in Python 3.11.
    # SQLite's stable primary codes are BUSY=5 and LOCKED=6. Older Python
    # exposes only the message. Never retry unrelated operational errors.
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        return code & 0xff in {5, 6}
    return str(error).lower() in {"database is locked", "database table is locked"}


def _enable_wal(db) -> None:
    # Concurrent first opens can fail journal-mode negotiation without invoking
    # SQLite's busy handler. Retry only that startup step within the same limit.
    deadline = time.monotonic() + LEDGER_BUSY_TIMEOUT_MS / 1000
    while True:
        try:
            db.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as error:
            remaining = deadline - time.monotonic()
            if not _is_locked(error) or remaining <= 0:
                raise
            time.sleep(min(.05, remaining))


class BudgetError(RuntimeError):
    pass


class BudgetExceeded(BudgetError):
    pass


def _cap(provider: str) -> dict:
    try:
        cap = json.loads((Path.home() / ".stormscore/caps.json").read_text())[provider]
        start, warn, stop = (float(cap[k]) for k in ("start_usd", "warn_at", "stop_at"))
        if not all(math.isfinite(n) for n in (start, warn, stop)):
            raise ValueError
        if not (start > 0 and 0 <= warn < stop <= 1):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise BudgetError(f"Missing or invalid budget cap for {provider}") from None
    return {"start_usd": start, "warn_at": warn, "stop_at": stop}


@contextmanager
def _ledger():
    directory = Path.home() / ".stormscore"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(directory / "ledger.sqlite",
                         timeout=LEDGER_BUSY_TIMEOUT_MS / 1000, isolation_level=None)
    try:
        db.execute(f"PRAGMA busy_timeout={LEDGER_BUSY_TIMEOUT_MS}")
        _enable_wal(db)
        db.execute("""CREATE TABLE IF NOT EXISTS ai_calls (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            provider TEXT NOT NULL, model TEXT NOT NULL, purpose TEXT NOT NULL,
            input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
            reserved_usd REAL NOT NULL, cost_usd REAL NOT NULL,
            status TEXT NOT NULL
        )""")
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def reserve(provider: str, model: str, input_tokens: int, max_tokens: int,
            purpose: str) -> str:
    # Modal runtime is capped by Modal itself. Do not require or alter a token
    # cap for a provider whose token price is zero; still record every call.
    cap = None if provider == "modal" else _cap(provider)
    estimate = cost_usd(model, input_tokens, max_tokens, provider=provider)
    call_id = uuid.uuid4().hex
    with _ledger() as db:
        rows = db.execute(
            "SELECT cost_usd FROM ai_calls WHERE provider = ?",
            (provider,),
        ).fetchall()
        used = sum((Decimal(str(row[0])) for row in rows), Decimal(0))
        projected = used + Decimal(str(estimate))
        start = Decimal(str(cap["start_usd"])) if cap is not None else None
        if cap is not None and projected >= start * Decimal(str(cap["stop_at"])):
            raise BudgetExceeded(f"{provider} call refused: budget stop threshold reached")
        if cap is not None and projected >= start * Decimal(str(cap["warn_at"])):
            print(f"Warning: {provider} budget at or above warning threshold", file=sys.stderr)
        db.execute(
            "INSERT INTO ai_calls (id, provider, model, purpose, input_tokens, "
            "output_tokens, reserved_usd, cost_usd, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (call_id, provider, model, purpose, input_tokens, max_tokens,
             estimate, estimate, "pending"),
        )
    return call_id


def settle(call_id: str, *, input_tokens: int, output_tokens: int) -> float:
    with _ledger() as db:
        row = db.execute("SELECT model, status, provider FROM ai_calls WHERE id = ?", (call_id,)).fetchone()
        if row is None or row[1] != "pending":
            raise BudgetError("Unknown or already settled reservation")
        actual = cost_usd(row[0], input_tokens, output_tokens, provider=row[2])
        db.execute(
            "UPDATE ai_calls SET input_tokens=?, output_tokens=?, cost_usd=?, status='complete' WHERE id=?",
            (input_tokens, output_tokens, actual, call_id),
        )
    return actual


def failed(call_id: str, *, definitely_unbilled: bool = False) -> None:
    with _ledger() as db:
        if definitely_unbilled:
            db.execute("UPDATE ai_calls SET cost_usd=0, status='rejected' WHERE id=? AND status='pending'",
                       (call_id,))
        else:
            db.execute("UPDATE ai_calls SET status='uncertain' WHERE id=? AND status='pending'", (call_id,))


def spent(provider: str) -> float:
    with _ledger() as db:
        return db.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM ai_calls WHERE provider=?",
                          (provider,)).fetchone()[0]
