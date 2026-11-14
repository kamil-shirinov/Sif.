"""List provider model IDs and make one tiny, budget-guarded call each."""

import argparse
import os
import time

from . import budget, llm


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    llm.load_environment()
    providers = ["meta", "fireworks", "modal"] if llm.live_enabled(args.live) else ["mock"]
    errors = 0
    for provider in providers:
        if provider == "modal" and not os.getenv("MODAL_BASE_URL"):
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
            result = llm.complete([{"role": "user", "content": "Reply OK."}], provider=provider,
                                  model=selected, max_tokens=8, purpose="smoke", live=args.live)
            elapsed = time.perf_counter() - started
            if not result["text"].strip() or result["tool_calls"]:
                raise llm.GatewayError("Empty or unexpected smoke response")
            print(f"{provider}: ok model={result['model']} latency_s={elapsed:.3f} cost_usd={result['cost_usd']:.8f}")
        except (llm.GatewayError, budget.BudgetError) as error:
            # These are gateway-owned, sanitized messages; never render SDK errors.
            print(f"{provider}: failed ({error})")
            errors += 1
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
