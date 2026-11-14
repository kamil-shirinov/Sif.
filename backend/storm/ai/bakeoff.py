"""Compare radio officer models on local replay bundles (offline by default)."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import time

from . import budget, llm
from .report import facts_from_bundle, write_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--details", action="store_true", help="Include each replay's check outcomes and audit issues, without book facts or report text")
    parser.add_argument("--fx-only", action="store_true", help="Only real SGX FX replays; exclude mock and equities")
    parser.add_argument("--expected-bundles", type=int, help="Refuse to run unless exactly this many bundles match")
    parser.add_argument("--models", nargs="+", required=True,
                        help="Model IDs, optionally provider:id, space- or comma-separated")
    parser.add_argument("--bundles", type=Path,
                        default=Path(__file__).resolve().parents[3] / "web/public/bundles")
    args = parser.parse_args(argv)
    bundles = []
    for path in sorted(args.bundles.glob("*.json")):
        if path.name == "index.json":
            continue
        bundle = json.loads(path.read_text())
        if args.fx_only and (bundle.get("source") != "sgx" or bundle.get("symbol") not in {"EURUSD", "USDJPY", "USDSGD"}):
            continue
        bundles.append((path.stem, facts_from_bundle(bundle)))
    if not bundles:
        print(f"No replay bundles found in {args.bundles}")
        return 1
    if args.expected_bundles is not None and len(bundles) != args.expected_bundles:
        print(f"Expected {args.expected_bundles} replay bundles; found {len(bundles)}")
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
        results, latencies, costs, details = [], [], [], []
        errors = 0
        for storm_id, facts in bundles:
            started = time.perf_counter()
            try:
                result = write_report(facts, live=args.live, model=selected, provider=provider)
                results.append(result)
                costs.append(result["cost_usd"])
                latencies.append(time.perf_counter() - started)
                initial_audit = result["inspector"].get("initial_audit", result["inspector"])
                details.append({"storm_id": storm_id, "outcome": result["outcome"],
                                "facts_sha256": hashlib.sha256(json.dumps(facts, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                                "first_try_numbers_verified": result["first_try_verified"],
                                "attempt_checks": result["attempt_checks"],
                                "initial_inspector_verdict": initial_audit["verdict"],
                                "initial_inspector_issues": initial_audit["issues"],
                                "final_inspector_verdict": result["inspector"]["verdict"],
                                "fallback": result["fallback"]})
            except (llm.GatewayError, budget.BudgetError) as error:
                print(f"{model}: failed ({error})")
                errors += 1
                failed = True
        flags = sum(result["inspector"]["verdict"] == "flag" or
                    result["inspector"].get("initial_audit", {}).get("verdict") == "flag"
                    for result in results)
        print(json.dumps({
            "model": model, "reports": len(results), "errors": errors,
            "private_mode": llm.private_mode(),
            "inspector_models": sorted({r["inspector"]["model"] for r in results}),
            "first_try_verification_rate": sum(r["first_try_verified"] for r in results) / len(bundles),
            "inspector_flags": flags,
            "outcome_counts": dict(Counter(r["outcome"] for r in results)),
            "mean_latency_s": statistics.mean(latencies) if latencies else None,
            "mean_writer_latency_s": statistics.mean(r["writer_latency_s"] for r in results) if results else None,
            "cost_per_report_usd": statistics.mean(costs) if costs else None,
            "fallbacks": sum(r["fallback"] for r in results),
            **({"details": details} if args.details else {}),
        }, sort_keys=True))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
