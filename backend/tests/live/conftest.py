import socket

import pytest

# Captured at import, before tests/conftest.py's per-test fixture patches the sockets.
_REAL = {
    "connect": socket.socket.connect,
    "create_connection": socket.create_connection,
    "getaddrinfo": socket.getaddrinfo,
}


@pytest.fixture
def real_network(monkeypatch, offline_models):
    """Opt in to the network for the one test that talks to Tiger (read-only)."""
    monkeypatch.setattr(socket.socket, "connect", _REAL["connect"])
    monkeypatch.setattr(socket, "create_connection", _REAL["create_connection"])
    monkeypatch.setattr(socket, "getaddrinfo", _REAL["getaddrinfo"])
