"""Offline privacy, credential and accounting regressions; no real ledger/env."""

import json
from pathlib import Path
import socket
import sqlite3

import pytest

try:
    import httpx2 as httpx
except ImportError:
    import httpx

from storm.ai import budget, llm, navigator, report
from storm.ai.prices import cost_usd


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("LLM_PRIVATE_MODE", "0")
    for name in ("MODAL_MODEL", "MODAL_BASE_URL", "MODAL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "load_environment", lambda: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Network forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


def fake_sdk(monkeypatch, handler):
    real_client = llm.OpenAI

    def client(**kwargs):
        return real_client(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(llm, "OpenAI", client)
    monkeypatch.setenv("MODAL_API_KEY", "offline-modal-placeholder")
    monkeypatch.setenv("MODAL_BASE_URL", "https://private.invalid/v1")


def completion(content="OK", calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"id": "offline", "object": "chat.completion", "created": 0, "model": "Qwen/Qwen3-8B",
            "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "stop", "message": message}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}}


def test_modal_sends_credential_and_never_charges_tokens(monkeypatch):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer offline-modal-placeholder"
        assert str(request.url) == "https://private.invalid/v1/chat/completions"
        return httpx.Response(200, json=completion())

    fake_sdk(monkeypatch, handler)
    result = llm.complete([{"role": "user", "content": "Hello"}], provider="modal",
                          max_tokens=64, purpose="test", live=True, reasoning_effort="low")
    assert seen[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "reasoning_effort" not in seen[0]
    assert result["cost_usd"] == budget.spent("modal") == 0
    assert cost_usd("Qwen/Qwen3-8B", 1000, 1000) > 0
    assert cost_usd("anything", 1000, 1000, provider="modal") == 0
    with pytest.raises(ValueError):
        cost_usd("anything", -1, 0, provider="modal")


def test_private_report_keeps_writer_and_inspector_on_modal(monkeypatch):
    bundle = json.loads((Path(__file__).resolve().parents[2] / "contracts/mock_storm.json").read_text())
    facts = report.facts_from_bundle(bundle)
    seen = []
    monkeypatch.setenv("LLM_PRIVATE_MODE", "1")

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        assert request.url.host == "private.invalid"
        text = (report.deterministic_report(facts) if len(seen) == 1
                else '{"verdict":"ok","issues":[]}')
        return httpx.Response(200, json=completion(text))

    fake_sdk(monkeypatch, handler)
    result = report.write_report(facts, live=True)
    assert result["verified"] and result["inspector"]["verdict"] == "ok"
    assert len(seen) == 2
    assert all(item["model"] == "Qwen/Qwen3-8B" for item in seen)
    assert result["cost_usd"] == budget.spent("modal") == 0


def test_private_navigator_keeps_tools_and_inspector_on_modal(monkeypatch):
    monkeypatch.setenv("LLM_PRIVATE_MODE", "1")
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        assert payload["model"] == "Qwen/Qwen3-8B"
        assert request.url.host == "private.invalid"
        if len(seen) == 1:
            return httpx.Response(200, json=completion(None, [{"id": "call1", "type": "function",
                "function": {"name": "list_storms", "arguments": "{}"}}]))
        if len(seen) == 2:
            return httpx.Response(200, json=completion(
                "The synthetic book has available replay data. Choose a replay to inspect exposure."))
        return httpx.Response(200, json=completion('{"verdict":"ok","issues":[]}'))

    fake_sdk(monkeypatch, handler)
    result = navigator.ask("List available storms", live=True)
    assert result["verified"] and result["inspector"]["verdict"] == "ok"
    assert len(seen) == 3


def test_private_failure_never_falls_back_to_another_provider(monkeypatch):
    monkeypatch.setenv("LLM_PRIVATE_MODE", "1")
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503, json={"error": {"message": "unavailable"}})

    fake_sdk(monkeypatch, handler)
    with pytest.raises(llm.GatewayError, match="modal completion failed"):
        llm.complete([{"role": "user", "content": "private"}], provider="meta",
                     model="provider-model", max_tokens=64, purpose="test", live=True)
    assert len(requests) == 3
    assert all(request.url.host == "private.invalid" for request in requests)
    assert budget.spent("modal") == 0


def test_private_model_discovery_and_missing_config_fail_closed(monkeypatch):
    monkeypatch.setenv("LLM_PRIVATE_MODE", "1")
    assert llm.resolve_model("fireworks", "hosted-model") == "Qwen/Qwen3-8B"
    with pytest.raises(llm.GatewayError, match="MODAL_API_KEY"):
        llm.complete([{"role": "user", "content": "private"}], provider="fireworks",
                     max_tokens=32, purpose="test", live=True)

    def handler(request):
        assert request.url.host == "private.invalid"
        return httpx.Response(200, json={"object": "list", "data": [{
            "id": "Qwen/Qwen3-8B", "object": "model", "created": 0, "owned_by": "private"}]})

    fake_sdk(monkeypatch, handler)
    assert llm.list_models("fireworks", live=True) == ["Qwen/Qwen3-8B"]


def test_private_mode_preserves_offline_default(monkeypatch):
    monkeypatch.setenv("LLM_PRIVATE_MODE", "1")
    result = llm.complete([{"role": "user", "content": "Hello"}], provider="meta",
                          max_tokens=32, purpose="test")
    assert result["provider"] == "mock"
    assert not (Path.home() / ".stormscore").exists()


def test_environment_uses_explicit_file_without_overriding(monkeypatch):
    # Inspect loader arguments; never read a real env file.
    import importlib
    loader = importlib.reload(llm)
    seen = []
    monkeypatch.setattr(loader, "load_dotenv", lambda path, **kwargs: seen.append((path, kwargs)))
    monkeypatch.setenv("STORM_ENV_FILE", "~/private-env-placeholder")
    loader.load_environment()
    assert seen == [(Path("~/private-env-placeholder").expanduser(), {"override": False})]


def test_python310_wal_lock_without_errorcode_retries(monkeypatch):
    attempts = []
    pauses = []

    class Connection:
        def execute(self, sql):
            attempts.append(sql)
            if len(attempts) == 1:
                raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(budget.time, "sleep", pauses.append)
    budget._enable_wal(Connection())
    assert attempts == ["PRAGMA journal_mode=WAL"] * 2
    assert pauses == [.05]


def test_wal_unrelated_error_is_not_retried(monkeypatch):
    class Connection:
        def execute(self, sql):
            raise sqlite3.OperationalError("unrelated failure")

    monkeypatch.setattr(budget.time, "sleep", lambda _: pytest.fail("Unexpected retry"))
    with pytest.raises(sqlite3.OperationalError, match="unrelated failure"):
        budget._enable_wal(Connection())


def test_server_redacts_vllm_startup_arguments(monkeypatch, capsys):
    import importlib.util
    import io
    import subprocess
    import threading

    spec = importlib.util.spec_from_file_location("llm_server", Path(__file__).with_name("llm_server.py"))
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    monkeypatch.setenv("MODAL_API_KEY", "offline-startup-placeholder")
    commands = []

    class Process:
        stdout = io.StringIO("api_key='offline-startup-placeholder'\nserver ready\n")

    def popen(command, **kwargs):
        commands.append(command)
        return Process()

    class ImmediateThread:
        def __init__(self, *, target, **kwargs):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    server.serve.local()
    assert "--api-key" in commands[0]
    assert "--disable-log-requests" in commands[0]
    assert "--disable-uvicorn-access-log" in commands[0]
    output = capsys.readouterr().out
    assert "offline-startup-placeholder" not in output
    assert "[redacted]" in output


def test_gpu_usage_integrates_allocations_and_marks_missing():
    import importlib.util
    import sys
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    folder = Path(__file__).parent
    sys.path.insert(0, str(folder))
    try:
        spec = importlib.util.spec_from_file_location("gpu_usage", folder / "gpu_usage.py")
        usage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(usage)
    finally:
        sys.path.remove(str(folder))
    start = datetime(2026, 11, 14, tzinfo=timezone.utc)
    metrics = SimpleNamespace(since=start, until=start + timedelta(minutes=3),
        bucket_size=timedelta(minutes=1), point_count=57,
        series={"gpu_count_l4_avg": SimpleNamespace(points=[
            SimpleNamespace(value=value) for value in [0.5, 1.0, None]])})
    summary = usage.summarize(metrics)
    assert summary["allocated_gpu_minutes_observed"] == {"gpu_count_l4_avg": 1.5}
    assert summary["missing_buckets"] == {"gpu_count_l4_avg": 1}
