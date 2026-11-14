"""List provider model IDs and make one tiny, budget-guarded call each."""

import argparse
import json
import os
import time

from . import budget, llm


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--provider", choices=sorted(llm.PROVIDERS),
                        help="Exercise only this provider (private mode always routes to Modal)")
    args = parser.parse_args(argv)
    llm.load_environment()
    providers = ["meta", "fireworks", "modal"] if llm.live_enabled(args.live) else ["mock"]
    if args.provider:
        providers = [args.provider]
    if llm.private_mode() and llm.live_enabled(args.live):
        providers = ["modal"]
    errors = 0
    for provider in providers:
        if provider == "modal" and not os.getenv("MODAL_BASE_URL") and not (args.provider or llm.private_mode()):
            print("modal: skipped (not configured)")
            continue
        try:
            ids = llm.list_models(provider, live=args.live)
            print(f"{provider} models: {', '.join(ids) or '(none)'}")
            try:
                selected = llm.resolve_model(provider)
            except llm.GatewayError:
                if not ids:
                    raise
                selected = ids[0]
            started = time.perf_counter()
            effort = {"meta": "minimal", "fireworks": "low"}.get(provider)
            result = llm.complete([{"role": "user", "content": "Reply with exactly one word: OK"}], provider=provider,
                                  model=selected, max_tokens=1024, purpose="smoke", live=args.live,
                                  reasoning_effort=effort)
            elapsed = time.perf_counter() - started
            if not result["text"].strip():
                raise llm.GatewayError("Empty smoke response", diagnostics=result)
            print(f"{provider}: ok model={result['model']} latency_s={elapsed:.3f} cost_usd={result['cost_usd']:.8f}")
        except (llm.GatewayError, budget.BudgetError) as error:
            # These are gateway-owned, sanitized messages; never render SDK errors.
            print(f"{provider}: failed ({error})")
            diagnostics = getattr(error, "diagnostics", {})
            print(json.dumps({"finish_reason": diagnostics.get("finish_reason"),
                              "usage": diagnostics.get("usage", {}),
                              "raw_message": diagnostics.get("raw_message", "")[:200]}))
            errors += 1
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
