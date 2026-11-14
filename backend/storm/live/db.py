"""Tiger Data connection helpers. The URL is read from the environment and never printed."""
from __future__ import annotations

import os
import re
import threading

import psycopg
from dotenv import load_dotenv

from ..paths import REPO_ROOT

ENV_FILE = REPO_ROOT / ".env"
URL_VAR = "TIGER_DATABASE_URL"
_URL = re.compile(r"postgres(?:ql)?://\S+")


class TigerConfigError(RuntimeError):
    pass


def database_url() -> str:
    load_dotenv(ENV_FILE, override=False)
    url = os.environ.get(URL_VAR, "")
    if not url.startswith("postgres"):
        raise TigerConfigError(f"{URL_VAR} is not set in {ENV_FILE.name}")
    return url


def env_file_has_url() -> bool:
    """True when .env exists and holds a Tiger URL (value is never returned)."""
    try:
        return any(line.startswith(f"{URL_VAR}=postgres") for line in ENV_FILE.read_text().splitlines())
    except OSError:
        return False


def scrub(message: object) -> str:
    """Remove anything URL-shaped, and the configured URL itself, from an error text."""
    text = _URL.sub("<url>", str(message))
    url = os.environ.get(URL_VAR, "")
    return text.replace(url, "<url>") if url else text


def connect(*, autocommit: bool = False, timeout: int = 15) -> psycopg.Connection:
    return psycopg.connect(database_url(), autocommit=autocommit, connect_timeout=timeout)


class SharedConnection:
    """One autocommit connection shared by request threads under a lock.

    The API's queries are short and read-only, so serialising them is simpler than a
    pool (psycopg_pool is not a project dependency). A broken connection is replaced
    once per call.
    """

    def __init__(self, timeout: int = 5):
        self._lock = threading.Lock()
        self._conn: psycopg.Connection | None = None
        self._timeout = timeout

    def _open(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = connect(autocommit=True, timeout=self._timeout)
        return self._conn

    def fetch(self, sql: str, params: tuple | list | None = None) -> list[tuple]:
        with self._lock:
            for attempt in (0, 1):
                try:
                    with self._open().cursor() as cur:
                        cur.execute(sql, params)
                        return cur.fetchall() if cur.description else []
                except psycopg.OperationalError:
                    self.close_unlocked()
                    if attempt:
                        raise
            return []

    def close_unlocked(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def close(self) -> None:
        with self._lock:
            self.close_unlocked()
