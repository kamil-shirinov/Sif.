"""The only entry point for model inference and provider model discovery."""

import json
import os
from pathlib import Path
import time

from dotenv import find_dotenv, load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI

from . import budget
from .prices import cost_usd


PROVIDERS = {"meta", "fireworks", "modal", "mock"}
MAX_INPUT_TOKENS = 60_000


class GatewayError(RuntimeError):
    """Sanitized error: SDK errors may contain request bodies or credentials."""

    def __init__(self, message: str, *, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


def _result(*, text: str, calls: list, provider: str, model: str,
            incoming: int, outgoing: int, charged: float, finish_reason: str,
            message: dict, usage: dict | None = None) -> dict:
    # Whitelist assistant fields; never include HTTP metadata or arbitrary SDK
    # extras. Redact configured credentials before taking a diagnostic preview.
    preview = json.dumps({key: message[key] for key in
                          ("role", "content", "refusal", "reasoning_content") if key in message},
                         ensure_ascii=False)
    for prefix in ("META", "FIREWORKS", "MODAL", "OPENAI"):
        secret = os.getenv(f"{prefix}_API_KEY")
        if secret:
            preview = preview.replace(secret, "[redacted]")
    diagnostics = {"finish_reason": finish_reason,
                   "usage": usage or {"prompt_tokens": incoming, "completion_tokens": outgoing,
                                      "total_tokens": incoming + outgoing},
                   "raw_message": preview[:200]}
    if finish_reason == "length" and not text.strip() and not calls:
        raise GatewayError(
            f"{provider} max_tokens was used up by reasoning before producing text; increase max_tokens",
            diagnostics=diagnostics,
        )
    return {"text": text, "tool_calls": calls, "provider": provider, "model": model,
            "input_tokens": incoming, "output_tokens": outgoing, "cost_usd": charged, **diagnostics}


def load_environment() -> None:
    # Called at use time, not at import, and never renders environment values.
    env_file = os.getenv("STORM_ENV_FILE")
    load_dotenv(Path(env_file).expanduser() if env_file else find_dotenv(usecwd=True), override=False)


def private_mode() -> bool:
    """All live crew roles stay on our Modal GPU, with no provider fallback."""
    return os.getenv("LLM_PRIVATE_MODE", "0").lower() in {"1", "true", "yes"}


def _route(provider: str, model: str | None = None) -> tuple[str, str | None]:
    if private_mode() and provider not in {"mock", "modal"}:
        return "modal", None
    return provider, model


def live_enabled(live: bool = False) -> bool:
    return live or os.getenv("LLM_MODE", "mock").lower() == "live"


def resolve_model(provider: str, model: str | None = None) -> str:
    provider, model = _route(provider, model)
    if model:
        return model
    if provider == "mock":
        return "mock"
    if provider == "meta":
        return os.getenv("META_MODEL") or "muse-spark-1.3"
    if provider == "modal":
        return os.getenv("MODAL_MODEL") or "Qwen/Qwen3-8B"
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
        # Cold starts include loading weights. Other providers retain the short
        # timeout. SDK retries remain disabled: the gateway owns reservations.
        return OpenAI(api_key=key, base_url=url, max_retries=0,
                      timeout=600.0 if provider == "modal" else 30.0)
    except Exception:
        raise GatewayError(f"{provider} client configuration failed") from None


def estimate_input_tokens(messages: list[dict], tools: list[dict] | None = None) -> int:
    # UTF-8 bytes are an upper bound for text BPE tokens. Include chat framing
    # and tool schemas instead of the unsafe common characters/4 heuristic.
    payload = json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False, allow_nan=False)
    return len(payload.encode("utf-8")) + 32 * len(messages) + 256


def _mock(messages: list[dict], purpose: str, tools: list[dict] | None) -> tuple[str, list, str]:
    if purpose == "storm-navigator":
        from .navigator import mock_completion
        return mock_completion(messages)
    if purpose == "navigator-answer":
        from .navigator import deterministic_answer
        return deterministic_answer(json.loads(messages[-1]["content"])["facts"]), [], "stop"
    if purpose == "navigator-inspector":
        from .navigator import deterministic_answer
        from .verify import verify_numbers
        payload = json.loads(messages[-1]["content"])
        issues = []
        if not verify_numbers(payload["text"], payload["facts"], allow_direction_words=True)["verified"]:
            issues.append("Answer contains unsupported numbers")
        if payload["text"] != deterministic_answer(payload["facts"]):
            issues.append("Mock inspector only certifies the deterministic navigator template")
        return json.dumps({"verdict": "flag" if issues else "ok", "issues": issues}), [], "stop"
    if messages[-1].get("role") == "tool":
        return str(messages[-1].get("content", "")), [], "stop"
    if tools:
        function = tools[0]["function"]
        # A caller may supply mock_arguments to exercise a deterministic tool
        # invocation; never execute a tool in the gateway itself.
        arguments = function.get("mock_arguments", {})
        return "", [{"id": "mock_call_1", "type": "function", "function": {
            "name": function["name"], "arguments": json.dumps(arguments, sort_keys=True)}}], "tool_calls"
    if purpose == "storm-report":
        return " ".join(json.loads(messages[-1]["content"])["facts"]["report_sentences"]), [], "stop"
    if purpose == "storm-inspector":
        from .report import deterministic_report
        from .verify import verify_numbers
        payload = json.loads(messages[-1]["content"])
        issues = []
        if not verify_numbers(payload["text"], payload["facts"], allow_direction_words=True)["verified"]:
            issues.append("Report contains unsupported numbers")
        if payload["text"] != deterministic_report(payload["facts"]):
            issues.append("Mock inspector only certifies the deterministic facts template")
        return json.dumps({"verdict": "flag" if issues else "ok", "issues": issues}), [], "stop"
    return "Mock response.", [], "stop"


def complete(messages, *, provider="mock", model=None, max_tokens, purpose,
             live=False, tools=None, reasoning_effort=None) -> dict:
    if provider not in PROVIDERS:
        raise ValueError("Unsupported provider")
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError("An explicit positive max_tokens is required")
    if reasoning_effort is not None and reasoning_effort not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
        raise ValueError("Unsupported reasoning_effort")
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
        text, calls, finish_reason = _mock(messages, purpose, tools)
        return _result(text=text, calls=calls, provider="mock", model="mock", incoming=estimated,
                       outgoing=max_tokens if finish_reason == "length" else len(text.encode("utf-8")),
                       charged=0.0, finish_reason=finish_reason,
                       message={"role": "assistant", "content": text})

    provider, model = _route(provider, model)
    selected = resolve_model(provider, model)
    previous_cost = 0.0
    with _client(provider) as client:
        for attempt in range(3):
            call_id = budget.reserve(provider, selected, estimated, max_tokens, purpose)
            kwargs = {"model": selected, "messages": messages, "max_tokens": max_tokens}
            if tools is not None:
                kwargs["tools"] = tools
            if provider == "modal" and "qwen" in selected.lower():
                kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
            elif reasoning_effort is not None:
                # extra_body also works with SDK versions predating the named
                # reasoning_effort argument while using the same API field.
                kwargs["extra_body"] = {"reasoning_effort": reasoning_effort}
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as error:
                status = error.status_code if isinstance(error, APIStatusError) else None
                unbilled = status is not None and 400 <= status < 500 and status != 408
                budget.failed(call_id, definitely_unbilled=unbilled)
                if not unbilled:
                    previous_cost += cost_usd(selected, estimated, max_tokens, provider=provider)
                if (reasoning_effort is not None and status in (400, 422) and attempt < 2
                        and "reasoning_effort" in str(getattr(error, "body", ""))):
                    reasoning_effort = None
                    continue
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
                finish_reason = response.choices[0].finish_reason
                raw_message = message.model_dump(exclude_none=True)
            except Exception:
                raise GatewayError(f"{provider} returned an invalid completion") from None
            numbers = {"prompt_tokens": incoming, "completion_tokens": outgoing}
            for field in ("total_tokens", "reasoning_tokens"):
                value = getattr(usage, field, None)
                if type(value) is int:
                    numbers[field] = value
            details = getattr(usage, "completion_tokens_details", None)
            reasoning_tokens = getattr(details, "reasoning_tokens", None)
            if type(reasoning_tokens) is int:
                numbers["reasoning_tokens"] = reasoning_tokens
            numbers.setdefault("total_tokens", incoming + outgoing)
            return _result(text=text, calls=calls, provider=provider, model=selected, incoming=incoming,
                           outgoing=outgoing, charged=charged + previous_cost, finish_reason=finish_reason,
                           message=raw_message, usage=numbers)
    raise GatewayError("Completion failed")


def list_models(provider: str, *, live: bool = False) -> list[str]:
    if provider not in PROVIDERS:
        raise ValueError("Unsupported provider")
    load_environment()
    if provider == "mock" or not live_enabled(live):
        return ["mock"]
    provider, _ = _route(provider)
    try:
        with _client(provider) as client:
            return sorted(item.id for item in client.models.list())
    except Exception:
        raise GatewayError(f"{provider} model discovery failed") from None
