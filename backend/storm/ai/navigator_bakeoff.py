"""Fixed, scored live navigator comparisons; no inference outside the gateway.

Use --live explicitly. Output contains evaluation metadata, never replay bundles,
credentials, generated prose or book facts. Each question runs sequentially so
latency measures the demo path without benchmark concurrency contention.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import statistics
import time

from . import budget, llm, navigator, scenario
from .verify import verify_numbers

KIMI = "accounts/fireworks/models/kimi-k3p1-pro"
GLM = "accounts/fireworks/models/glm-5p3"
DEFAULT_MODELS = ["meta:muse-spark-1.3", "meta:muse-wonder-1.0",
                  "fireworks:accounts/fireworks/models/qwen3p8-max",
                  f"fireworks:{GLM}", f"fireworks:{KIMI}"]


def call(name, **arguments):
    return {"name": name, "arguments": arguments}


def cases():
    j, e, s = "usdjpy-2026-07-30", "eurusd-2026-08-07", "usdsgd-2026-08-07"
    return [
        ("stress-drop", "Stress USDJPY down 3% in 30 minutes on the default synthetic book.", j,
         [call("stress_test", symbol="USDJPY", move_pct=-3, minutes=30)]),
        ("stress-rise", "Stress EURUSD up 1.5% in 60 minutes on the default synthetic book.", e,
         [call("stress_test", symbol="EURUSD", move_pct=1.5, minutes=60)]),
        ("stress-small", "Stress USDSGD down 0.5% in 5 minutes on the default synthetic book.", s,
         [call("stress_test", symbol="USDSGD", move_pct=-0.5, minutes=5)]),
        ("scenario-short", f"Make a hypothetical USDJPY replay down 2% in 15 minutes shaped like {j}; compare the two ships.", j,
         [call("scenario", symbol="USDJPY", move_pct=-2, minutes=15, base_storm_id=j)]),
        ("scenario-long", f"Make a hypothetical EURUSD replay up 1% in 120 minutes shaped like {e}; compare the two ships.", e,
         [call("scenario", symbol="EURUSD", move_pct=1, minutes=120, base_storm_id=e)]),
        ("leverage-ten", "Stress USDJPY down 2% in 30 minutes with synthetic leverage of 10 times equity.", j,
         [call("stress_test", symbol="USDJPY", move_pct=-2, minutes=30, leverage=10)]),
        ("leverage-compare", "Compare endpoint stress for USDJPY down 2% in 30 minutes at 10 and 40 times synthetic leverage. Use both stress results.", j,
         [call("stress_test", symbol="USDJPY", move_pct=-2, minutes=30, leverage=v) for v in (10, 40)]),
        ("duration-compare", "Compare endpoint stress for USDSGD down 1% over 5 minutes versus 120 minutes on the default synthetic book. Does duration change endpoint P&L?", s,
         [call("stress_test", symbol="USDSGD", move_pct=-1, minutes=v) for v in (5, 120)]),
        ("exposure-then-stress", f"Inspect exposure in {e}, then stress EURUSD up 2% in 45 minutes on the default synthetic book. Describe both results.", e,
         [call("get_exposure", storm_id=e), call("stress_test", symbol="EURUSD", move_pct=2, minutes=45)]),
        ("two-storms", "Compare hypothetical USDJPY replays down 3% in 30 minutes, shaped respectively like usdjpy-2026-07-30 and usdjpy-2026-08-07. Compute both scenarios and describe both ship outcomes.", j,
         [call("scenario", symbol="USDJPY", move_pct=-3, minutes=30, base_storm_id=v)
          for v in (j, "usdjpy-2026-08-07")]),
    ]


def correct_tools(actual, expected):
    if not actual or any("error" in c["result"] for c in actual):
        return False
    for target in expected:
        if not any(c["name"] == target["name"] and all(c["arguments"].get(k) == v
                   for k, v in target["arguments"].items()) for c in actual):
            return False
    return True


@contextmanager
def checker(model):
    previous = os.environ.get("FIREWORKS_MODEL_CHECKER")
    os.environ["FIREWORKS_MODEL_CHECKER"] = model
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("FIREWORKS_MODEL_CHECKER", None)
        else:
            os.environ["FIREWORKS_MODEL_CHECKER"] = previous


def evaluate(model_id, *, live=False):
    provider, model = model_id.split(":", 1)
    details = []
    inspector = GLM if "kimi" in model.lower() else KIMI
    for case_id, question, storm_id, expected in cases():
        responses = []
        original = llm.complete

        def track(*args, **kwargs):
            result = original(*args, **kwargs)
            responses.append((kwargs["purpose"], result))
            return result

        started = time.perf_counter()
        row = {"case": case_id, "expected_calls": expected}
        llm.complete = track
        try:
            with checker(inspector):
                result = navigator.ask(question, storm_id, live=live, provider=provider, model=model)
            facts = {"tool_results": [{"name": c["name"], "result": c["result"]}
                                      for c in result["tool_calls"]]}
            drafts = [r["text"] for p, r in responses if p == "storm-navigator" and not r["tool_calls"]]
            first = drafts[0] if drafts else ""
            row.update(verified=result["verified"], correct_tool_use=correct_tools(result["tool_calls"], expected),
                       inspector_ok=result["inspector"]["verdict"] == "ok",
                       initial_inspector_ok=result["inspector"].get("initial_audit", result["inspector"])["verdict"] == "ok",
                       inspector_model=result["inspector"]["model"],
                       inspector_issues=result["inspector"]["issues"],
                       first_try_verified=bool(first) and verify_numbers(first, facts, allow_direction_words=True)["verified"],
                       fallback=result["answer"] == navigator.deterministic_answer(facts),
                       tool_calls=[{"name": c["name"], "arguments": c["arguments"],
                                    "error": c["result"].get("error")} for c in result["tool_calls"]])
        except (llm.GatewayError, budget.BudgetError, ValueError, RuntimeError) as error:
            row.update(error=str(error), verified=False, correct_tool_use=False, inspector_ok=False,
                       first_try_verified=False, fallback=False)
        finally:
            llm.complete = original
        row["latency_s"] = time.perf_counter() - started
        row["cost_usd"] = sum(r["cost_usd"] for _, r in responses)
        details.append(row)
        print(json.dumps({"progress": model_id, **row}), flush=True)
    return {"model": model_id, "private_mode": llm.private_mode(), "questions": len(details),
            **{key: sum(bool(r.get(key)) for r in details) for key in
               ("verified", "first_try_verified", "correct_tool_use", "inspector_ok", "initial_inspector_ok", "fallback")},
            "success": sum(r["verified"] and r["correct_tool_use"] and r["inspector_ok"] and not r["fallback"] for r in details),
            "errors": sum("error" in r for r in details),
            "mean_latency_s": statistics.mean(r["latency_s"] for r in details),
            "under_15_s": sum(r["latency_s"] < 15 for r in details),
            "cost_usd": sum(r["cost_usd"] for r in details), "details": details}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    llm.load_environment()
    scenario.BUNDLES_DIR = args.bundles
    # Fail before spending if a required replay is missing or invalid.
    for _, _, storm_id, expected in cases():
        scenario.load_bundle(storm_id)
        for item in expected:
            if item["name"] == "scenario":
                scenario.load_bundle(item["arguments"]["base_storm_id"])
    results = []
    for model in args.models:
        result = evaluate(model, live=args.live)
        results.append(result)
        args.out.write_text(json.dumps({"models": results}, indent=2, allow_nan=False) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "details"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
