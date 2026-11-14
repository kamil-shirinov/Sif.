"""AI tests must never touch the real ledger, .env, or network."""

import json
from pathlib import Path
import socket

import pytest

from storm.ai import llm


@pytest.fixture(autouse=True)
def isolated_ai(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LLM_MODE", "mock")
    for name in ("META_MODEL", "FIREWORKS_MODEL_CHECKER", "MODAL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "load_environment", lambda: None)

    def offline(*args, **kwargs):
        raise AssertionError("Network access is forbidden in AI tests")

    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(socket, "create_connection", offline)
    monkeypatch.setattr(socket, "getaddrinfo", offline)


@pytest.fixture
def caps(tmp_path):
    directory = tmp_path / ".stormscore"
    directory.mkdir()
    path = directory / "caps.json"
    path.write_text(json.dumps({provider: {"start_usd": 1, "warn_at": .75, "stop_at": .90}
                                for provider in ("meta", "fireworks", "modal")}))
    return path


@pytest.fixture
def bundle():
    return json.loads((Path(__file__).resolve().parents[3] / "contracts/mock_storm.json").read_text())
