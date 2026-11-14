"""The only entry point for model inference and provider model discovery."""

import json
import os
import time

from dotenv import find_dotenv, load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI

from . import budget
from .prices import cost_usd


PROVIDERS = {"meta", "fireworks", "modal", "mock"}
MAX_INPUT_TOKENS = 60_000


class GatewayError(RuntimeError):
    """Sanitized error: SDK errors may contain request bodies or credentials."""


def load_environment() -> None:
    # Called at use time, not at import, and never renders environment values.
    load_dotenv(find_dotenv(usecwd=True), override=False)


def live_enabled(live: bool = False) -> bool:
    return live or os.getenv("LLM_MODE", "mock").lower() == "live"


def resolve_model(provider: str, model: str | None = None) -> str:
    if model:
        return model
    if provider == "mock":
        return "mock"
    if provider == "meta":
        return os.getenv("META_MODEL") or "muse-spark-1.1"
    variable = {"fireworks": "FIREWORKS_MODEL_CHECKER", "modal": "MODAL_MODEL"}[provider]
    value = os.getenv(variable)
    if not value:
        raise GatewayError(f"Configure {variable} or pass a model ID")
    return value


def _client(provider: str) -> OpenAI:
    prefix = provider.upper()
    key = os.getenv(f"{prefix}_API_KEY")
    url = os.getenv(f"{prefix}_BASE_URL")
    if not key or not url:
        raise GatewayError(f"Configure {prefix}_API_KEY and {prefix}_BASE_URL")
    try:
        return OpenAI(api_key=key, base_url=url, max_retries=0, timeout=30.0)
    except Exception:
        raise GatewayError(f"{provider} client configuration failed") from None


def estimate_input_tokens(messages: list[dict], tools: list[dict] | None = None) -> int:
    # UTF-8 bytes are an upper bound for text BPE tokens. Include chat framing
    # and tool schemas instead of the unsafe common characters/4 heuristic.
    payload = json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False, allow_nan=False)
    return len(payload.encode("utf-8")) + 32 * len(messages) + 256


def _mock(messages: list[dict], purpose: str, tools: list[dict] | None) -> tuple[str, list]:
    if messages[-1].get("role") == "tool":
        return str(messages[-1].get("content", "")), []
    if tools:
        function = tools[0]["function"]
        # A caller may supply mock_arguments to exercise a deterministic tool
        # invocation; never execute a tool in the gateway itself.
        arguments = function.get("mock_arguments", {})
        return "", [{"id": "mock_call_1", "type": "function", "function": {
            "name": function["name"], "arguments": json.dumps(arguments, sort_keys=True)}}]
    if purpose == "storm-report":
        from .report import deterministic_report
        return deterministic_report(json.loads(messages[-1]["content"])["facts"]), []
    if purpose == "storm-inspector":
        from .report import deterministic_report
        from .verify import verify_numbers
        payload = json.loads(messages[-1]["content"])
        issues = []
        if not verify_numbers(payload["text"], payload["facts"])["verified"]:
            issues.append("Report contains unsupported numbers")
        if payload["text"] != deterministic_report(payload["facts"]):
            issues.append("Mock inspector only certifies the deterministic facts template")
        return json.dumps({"verdict": "flag" if issues else "ok", "issues": issues}), []
    return "Mock response.", []


def complete(messages, *, provider="mock", model=None, max_tokens, purpose,
             live=False, tools=None) -> dict:
    if provider not in PROVIDERS:
        raise ValueError("Unsupported provider")
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError("An explicit positive max_tokens is required")
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 128:
        raise ValueError("Provide a short purpose label")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("role"), str):
            raise ValueError("Each message needs a role")
        if message.get("content") is not None and not isinstance(message["content"], str):
            raise ValueError("Only text content is supported by the token budget guard")
    estimated = estimate_input_tokens(messages, tools)
    if estimated > MAX_INPUT_TOKENS:
        raise ValueError("Input exceeds the conservative 60,000 token limit")
    load_environment()
    if provider == "mock" or not live_enabled(live):
        text, calls = _mock(messages, purpose, tools)
        return {"text": text, "tool_calls": calls, "provider": "mock", "model": "mock",
                "input_tokens": estimated, "output_tokens": len(text.encode("utf-8")), "cost_usd": 0.0}

    selected = resolve_model(provider, model)
    previous_cost = 0.0
    with _client(provider) as client:
        for attempt in range(3):
            call_id = budget.reserve(provider, selected, estimated, max_tokens, purpose)
            kwargs = {"model": selected, "messages": messages, "max_tokens": max_tokens}
            if tools is not None:
                kwargs["tools"] = tools
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as error:
                status = error.status_code if isinstance(error, APIStatusError) else None
                unbilled = status is not None and 400 <= status < 500 and status != 408
                budget.failed(call_id, definitely_unbilled=unbilled)
                if not unbilled:
                    previous_cost += cost_usd(selected, estimated, max_tokens)
                retryable = isinstance(error, APIConnectionError) or status in (408, 409, 429) or (
                    status is not None and status >= 500)
                if retryable and attempt < 2:
                    time.sleep(0.25 * 2 ** attempt)
                    continue
                raise GatewayError(f"{provider} completion failed after {attempt + 1} attempt(s)") from None
            # Account for a received response even if its content is malformed.
            usage = response.usage
            incoming = getattr(usage, "prompt_tokens", None)
            outgoing = getattr(usage, "completion_tokens", None)
            incoming = incoming if type(incoming) is int and incoming >= 0 else estimated
            outgoing = outgoing if type(outgoing) is int and outgoing >= 0 else max_tokens
            charged = budget.settle(call_id, input_tokens=incoming, output_tokens=outgoing)
            try:
                message = response.choices[0].message
                calls = [call.model_dump(exclude_none=True) for call in (message.tool_calls or [])]
                text = message.content or ""
            except Exception:
                raise GatewayError(f"{provider} returned an invalid completion") from None
            return {"text": text, "tool_calls": calls, "provider": provider, "model": selected,
                    "input_tokens": incoming, "output_tokens": outgoing,
                    "cost_usd": charged + previous_cost}
    raise GatewayError("Completion failed")


def list_models(provider: str, *, live: bool = False) -> list[str]:
    if provider not in PROVIDERS:
        raise ValueError("Unsupported provider")
    load_environment()
    if provider == "mock" or not live_enabled(live):
        return ["mock"]
    try:
        with _client(provider) as client:
            return sorted(item.id for item in client.models.list())
    except Exception:
        raise GatewayError(f"{provider} model discovery failed") from None
