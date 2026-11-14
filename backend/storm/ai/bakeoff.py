"""Compare radio officer models on local replay bundles (offline by default)."""

import argparse
import json
from pathlib import Path
import statistics
import time

from . import budget, llm
from .report import facts_from_bundle, write_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--models", nargs="+", required=True,
                        help="Model IDs, optionally provider:id, space- or comma-separated")
    parser.add_argument("--bundles", type=Path,
                        default=Path(__file__).resolve().parents[3] / "web/public/bundles")
    args = parser.parse_args(argv)
    bundles = []
    for path in sorted(args.bundles.glob("*.json")):
        if path.name == "index.json":
            continue
        bundles.append(facts_from_bundle(json.loads(path.read_text())))
    if not bundles:
        print(f"No replay bundles found in {args.bundles}")
        return 1
    failed = False
    for model in [item for argument in args.models for item in argument.split(",") if item]:
        provider, selected = "meta", model
        if ":" in model:
            provider, selected = model.split(":", 1)
            if provider not in llm.PROVIDERS or not selected:
                parser.error("Use meta:id, fireworks:id, modal:id, or mock:id")
        elif model.startswith("accounts/") or model.lower().startswith(("kimi-", "ember-", "deepseek-", "minimax-")):
            provider = "fireworks"
        results, latencies, costs = [], [], []
        errors = 0
        for facts in bundles:
            started = time.perf_counter()
            try:
                result = write_report(facts, live=args.live, model=selected, provider=provider)
                results.append(result)
                costs.append(result["cost_usd"])
                latencies.append(time.perf_counter() - started)
            except (llm.GatewayError, budget.BudgetError) as error:
                print(f"{model}: failed ({error})")
                errors += 1
                failed = True
        flags = sum(result["inspector"]["verdict"] == "flag" or
                    result["inspector"].get("initial_audit", {}).get("verdict") == "flag"
                    for result in results)
        print(json.dumps({
            "model": model, "reports": len(results), "errors": errors,
            "first_try_verification_rate": sum(r["first_try_verified"] for r in results) / len(bundles),
            "inspector_flags": flags,
            "mean_latency_s": statistics.mean(latencies) if latencies else None,
            "cost_per_report_usd": statistics.mean(costs) if costs else None,
            "fallbacks": sum(r["fallback"] for r in results),
        }, sort_keys=True))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
