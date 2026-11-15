import json
from pathlib import Path

from openai import OpenAI
import pytest

try:
    import httpx2 as httpx
except ImportError:
    import httpx

from storm.ai import budget, llm
from storm.ai.prices import cost_usd


MESSAGES = [{"role": "user", "content": "Hello"}]
TOOLS = [{"type": "function", "function": {
    "name": "get_exposure", "description": "Inspect the synthetic book",
    "parameters": {"type": "object", "properties": {}},
}}]


def sdk_client(monkeypatch, handler):
    def client(provider):
        return OpenAI(api_key="offline-test-placeholder", base_url="https://offline.invalid/v1",
                      max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(llm, "_client", client)


def response(*, tools=False, usage=True):
    data = {"id": "test", "object": "chat.completion", "created": 0, "model": "test-model",
            "choices": [{"index": 0, "finish_reason": "tool_calls" if tools else "stop",
                         "message": {"role": "assistant", "content": None if tools else "OK"}}]}
    if tools:
        data["choices"][0]["message"]["tool_calls"] = [
            {"id": "tool_1", "type": "function", "function": {"name": "get_exposure", "arguments": "{}"}}]
    if usage:
        data["usage"] = {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14,
                         "prompt_tokens_details": {"cached_tokens": 10}}
    return data


def test_offline_is_default_and_does_not_touch_ledger(monkeypatch):
    monkeypatch.setattr(llm, "_client", lambda provider: pytest.fail("SDK used while offline"))
    result = llm.complete(MESSAGES, provider="meta", max_tokens=8, purpose="test")
    assert result["provider"] == "mock" and result["cost_usd"] == 0
    assert not (Path.home() / ".stormscore").exists()


def test_mock_tool_calls_round_trip():
    result = llm.complete(MESSAGES, tools=TOOLS, max_tokens=64, purpose="navigator")
    call = result["tool_calls"][0]
    assert call["function"]["name"] == "get_exposure"
    assert json.loads(call["function"]["arguments"]) == {}
    followup = MESSAGES + [{"role": "assistant", "content": None, "tool_calls": result["tool_calls"]},
                           {"role": "tool", "tool_call_id": call["id"], "content": '{"leverage":20}'}]
    answer = llm.complete(followup, tools=TOOLS, max_tokens=64, purpose="navigator")
    assert answer["text"] == '{"leverage":20}' and answer["tool_calls"] == []


def test_sdk_tool_serialization_and_uncached_usage(caps, monkeypatch):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=response(tools=True))

    sdk_client(monkeypatch, handler)
    result = llm.complete(MESSAGES, provider="meta", tools=TOOLS,
                          max_tokens=32, purpose="navigator", live=True)
    assert requests[0]["tools"] == TOOLS
    assert requests[0]["max_tokens"] == 32
    assert result["tool_calls"][0]["function"]["arguments"] == "{}"
    assert result["input_tokens"] == 10 and result["output_tokens"] == 4
    assert result["cost_usd"] == cost_usd("muse-spark-1.1", 10, 4)
    assert budget.spent("meta") == result["cost_usd"]


def test_live_mode_environment_and_missing_usage(caps, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    sdk_client(monkeypatch, lambda request: httpx.Response(200, json=response(usage=False)))
    result = llm.complete(MESSAGES, provider="meta", max_tokens=8, purpose="test")
    assert result["input_tokens"] == llm.estimate_input_tokens(MESSAGES)
    assert result["output_tokens"] == 8
    assert budget.spent("meta") == result["cost_usd"]


def test_at_most_two_retries_with_backoff(caps, monkeypatch):
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "private provider detail", "type": "rate_limit"}})

    sdk_client(monkeypatch, handler)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    with pytest.raises(llm.GatewayError, match="3 attempt") as error:
        llm.complete(MESSAGES, provider="meta", max_tokens=8, purpose="test", live=True)
    assert len(calls) == 3 and sleeps == [.25, .5]
    assert "private provider detail" not in str(error.value)
    assert budget.spent("meta") == 0


def test_server_failure_reservation_is_charged_on_eventual_success(caps, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, json={"error": {"message": "uncertain"}}) if len(calls) == 1 else httpx.Response(200, json=response())

    sdk_client(monkeypatch, handler)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    result = llm.complete(MESSAGES, provider="meta", max_tokens=8, purpose="test", live=True)
    assert len(calls) == 2
    assert result["cost_usd"] == pytest.approx(
        cost_usd("muse-spark-1.1", llm.estimate_input_tokens(MESSAGES), 8) +
        cost_usd("muse-spark-1.1", 10, 4))
    assert budget.spent("meta") == pytest.approx(result["cost_usd"])


def test_budget_blocks_before_inference(caps, monkeypatch):
    requests = []
    sdk_client(monkeypatch, lambda request: requests.append(request))
    with pytest.raises(budget.BudgetExceeded):
        llm.complete(MESSAGES, provider="meta", max_tokens=1_000_000, purpose="test", live=True)
    assert requests == []


def test_limits_and_multimodal_input_are_rejected():
    with pytest.raises(ValueError, match="60,000"):
        llm.complete([{"role": "user", "content": "x" * 60_000}], max_tokens=8, purpose="test")
    with pytest.raises(ValueError, match="60,000"):
        llm.complete(MESSAGES, tools=[{"description": "x" * 60_000}], max_tokens=8, purpose="test")
    with pytest.raises(ValueError, match="text content"):
        llm.complete([{"role": "user", "content": [{"type": "image_url"}]}], max_tokens=8, purpose="test")
    with pytest.raises(TypeError):
        llm.complete(MESSAGES, purpose="test")
    with pytest.raises(ValueError, match="max_tokens"):
        llm.complete(MESSAGES, max_tokens=0, purpose="test")


def test_discovery_is_offline_by_default_and_uses_gateway(monkeypatch):
    assert llm.list_models("fireworks") == ["mock"]
    sdk_client(monkeypatch, lambda request: httpx.Response(200, json={
        "object": "list", "data": [{"id": "model-b", "object": "model", "created": 0, "owned_by": "test"},
                                    {"id": "model-a", "object": "model", "created": 0, "owned_by": "test"}]}))
    assert llm.list_models("fireworks", live=True) == ["model-a", "model-b"]


@pytest.mark.parametrize("content", ["", "   "])
def test_mock_empty_content_at_length_limit_is_a_clear_error(monkeypatch, content):
    monkeypatch.setattr(llm, "_mock", lambda *args: (content, [], "length"))
    with pytest.raises(llm.GatewayError, match="max_tokens was used up by reasoning") as error:
        llm.complete(MESSAGES, provider="mock", max_tokens=1024, purpose="smoke")
    assert error.value.diagnostics["finish_reason"] == "length"
    assert error.value.diagnostics["usage"]["completion_tokens"] == 1024
    assert len(error.value.diagnostics["raw_message"]) <= 200
    assert not (Path.home() / ".stormscore").exists()


def test_reasoning_only_response_is_charged_and_diagnostics_are_bounded(caps, monkeypatch):
    secret = "offline-secret-placeholder"
    monkeypatch.setenv("META_API_KEY", secret)
    data = response()
    data["choices"][0]["finish_reason"] = "length"
    data["choices"][0]["message"] = {
        "role": "assistant", "content": None,
        "reasoning_content": secret + " thinking" * 100,
        "headers": {"Authorization": "private-header-must-never-appear"},
    }
    data["usage"]["completion_tokens_details"] = {"reasoning_tokens": 4}
    sdk_client(monkeypatch, lambda request: httpx.Response(200, json=data))
    with pytest.raises(llm.GatewayError, match="reasoning") as error:
        llm.complete(MESSAGES, provider="meta", max_tokens=1024, purpose="smoke", live=True)
    assert budget.spent("meta") == cost_usd("muse-spark-1.1", 10, 4)
    diagnostics = error.value.diagnostics
    assert diagnostics["usage"]["reasoning_tokens"] == 4
    assert len(diagnostics["raw_message"]) == 200
    assert "[redacted]" in diagnostics["raw_message"]
    assert secret not in str(error.value) + json.dumps(diagnostics)
    assert "private-header" not in json.dumps(diagnostics)
    assert "Authorization" not in json.dumps(diagnostics)


@pytest.mark.parametrize("provider,status,limit,model", [
    ("meta", 400, 4096, "muse-spark-1.3"),
    ("fireworks", 422, 2048, "accounts/fireworks/models/kimi-k3p1-pro"),
])
def test_rejected_reasoning_effort_retries_without_it_under_budget_guard(
        caps, monkeypatch, provider, status, limit, model):
    requests, reservations = [], []
    reserve = budget.reserve

    def guarded(*args):
        reservations.append(args[3])
        return reserve(*args)

    def handler(request):
        requests.append(json.loads(request.content))
        assert len(reservations) == len(requests)
        if "reasoning_effort" in requests[-1]:
            return httpx.Response(status, json={"error": {
                "message": "Unsupported parameter: reasoning_effort", "param": "reasoning_effort"}})
        return httpx.Response(200, json=response())

    monkeypatch.setattr(budget, "reserve", guarded)
    sdk_client(monkeypatch, handler)
    result = llm.complete(MESSAGES, provider=provider, model=model, max_tokens=limit,
                          purpose="reasoning-test", live=True, reasoning_effort="low")
    assert requests[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in requests[1]
    assert reservations == [limit, limit]
    assert result["text"] == "OK"
    assert budget.spent(provider) == cost_usd(model, 10, 4)


def test_report_and_inspector_reserve_their_larger_output_limits(caps, bundle, monkeypatch):
    from storm.ai import report

    facts = report.facts_from_bundle(bundle)
    monkeypatch.setenv("FIREWORKS_MODEL_CHECKER", "accounts/fireworks/models/kimi-k3p1-pro")
    reserve = budget.reserve
    reservations = []

    def guarded(*args):
        reservations.append((args[0], args[3]))
        previous = budget.spent(args[0])
        call_id = reserve(*args)
        # The gateway reserves the full new reasoning+text output ceiling before
        # the mocked provider is invoked, not the smaller previous token limit.
        assert budget.spent(args[0]) - previous == pytest.approx(cost_usd(args[1], args[2], args[3]))
        return call_id

    def handler(request):
        payload = json.loads(request.content)
        data = response()
        is_writer = payload["model"].endswith("glm-5p3")
        data["choices"][0]["message"]["content"] = (
            report.deterministic_report(facts) if is_writer else '{"verdict":"ok","issues":[]}'
        )
        assert payload["max_tokens"] == reservations[-1][1]
        assert payload["reasoning_effort"] == "low"
        return httpx.Response(200, json=data)

    monkeypatch.setattr(budget, "reserve", guarded)
    sdk_client(monkeypatch, handler)
    assert report.write_report(facts, live=True)["verified"]
    assert reservations == [("fireworks", 4096), ("fireworks", 2048)]
