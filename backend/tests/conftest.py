import socket

import pytest

from storm.ai import llm
from storm.paths import RAW_DIR

USDJPY_SPOT_ZIP = RAW_DIR / "USDJPY_USD_SPOT_SPOT_1000000_20260701-20260831.zip"

needs_raw = pytest.mark.skipif(not USDJPY_SPOT_ZIP.exists(), reason="SGX data not in data/raw")


@pytest.fixture(autouse=True)
def offline_models(monkeypatch, tmp_path):
    """Backend tests never load .env, touch the real ledger, or reach a network."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setattr(llm, "load_environment", lambda: None)

    def offline(*args, **kwargs):
        raise AssertionError("Network access is forbidden in backend tests")

    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(socket, "create_connection", offline)
    monkeypatch.setattr(socket, "getaddrinfo", offline)
