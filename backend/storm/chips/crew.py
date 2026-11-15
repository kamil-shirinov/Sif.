"""Bounded real report crews on the identical staged replay facts."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from storm.ai import llm
from storm.ai.report import write_report
from storm.export import report_facts, write_bundle
from storm.paths import REPO_ROOT

from .protocol import DATA, DOCS, MAIN, canonical, check_frozen, save

TASK_ID = "cx-chips-20261115"
GLM = "accounts/fireworks/models/glm-5p3"
KIMI = "accounts/fireworks/models/kimi-k3p1-pro"
PRIVATE = "openai/gpt-oss-120b"
MODAL_RATE_BOUND = 0.002  # USD/second; conservative wall-time bound, not invoice
MODAL_DEADLINE_S = 3300  # <= $6.60 at the stated upper-bound rate


def environment(private: bool) -> None:
    os.environ["STORM_ENV_FILE"] = str(MAIN / ".env")
    llm.load_environment()
    os.environ.update(STORM_TASK_ID=TASK_ID,
                      STORM_TASK_LIMITS_JSON=json.dumps({"fireworks": 10, "modal": 10}),
                      LLM_PRIVATE_MODE="1" if private else "0",
                      REPORT_WRITER_PROVIDER="fireworks", REPORT_WRITER_MODEL=GLM,
                      FIREWORKS_MODEL_CHECKER=KIMI, MODAL_MODEL=PRIVATE)


def reports(private: bool) -> dict:
    environment(private)
    result = json.loads((DOCS / "results.json").read_text())
    path = DOCS / ("ai_private.json" if private else "ai_default.json")
    if path.exists():
        raise FileExistsError("Crew run already recorded; do not silently rerun")
    details = []
    for selected in result["replay_selection"]:
        name = selected["storm_id"] + ".json"
        bundle = json.loads((DATA / "bundles" / name).read_text())
        facts = report_facts(bundle)
        item = {"storm_id": bundle["storm_id"],
                "facts_sha256": hashlib.sha256(canonical(facts).encode()).hexdigest()}
        started = time.perf_counter()
        try:
            report = write_report(facts, live=True)
            item.update(status="complete", report=report, latency_s=time.perf_counter() - started)
            if not private:
                bundle["report"] = {"text": report["text"], "verified": bool(report["verified"]),
                                    "unverified_numbers": report["unverified_numbers"], "model": report["model"],
                                    "inspector": {k: report["inspector"][k] for k in ("verdict", "issues")}}
                write_bundle(bundle, DATA / "bundles")
        except Exception as error:
            # Gateway errors are sanitized by the gateway; arbitrary errors stay type-only.
            item.update(status="failed", error_type=type(error).__name__,
                        error=str(error) if isinstance(error, llm.GatewayError) else type(error).__name__,
                        latency_s=time.perf_counter() - started)
        details.append(item)
        save(DATA / ("private_progress.json" if private else "default_progress.json"), details)
        print(f"{'private' if private else 'default'} {bundle['storm_id']}: {item['status']}", flush=True)
    complete = [d for d in details if d["status"] == "complete"]
    outcomes = [d["report"] for d in complete]
    summary = {"crew": "private" if private else "default", "private_mode": private,
               "writer_model": PRIVATE if private else GLM,
               "inspector_models": sorted({r["inspector"]["model"] for r in outcomes}),
               "requested_reports": len(details), "reports": len(complete),
               "errors": len(details) - len(complete),
               "first_try_numbers_verified": sum(r["first_try_verified"] for r in outcomes),
               "first_try_verification_rate": sum(r["first_try_verified"] for r in outcomes) / len(details),
               "accepted_first_try": sum(r["outcome"] == "passed_first_try" for r in outcomes),
               "fallbacks": sum(r["fallback"] for r in outcomes),
               "inspector_flags": sum(r["inspector"].get("initial_audit", r["inspector"])["verdict"] == "flag"
                                      for r in outcomes),
               "outcomes": dict(Counter(r["outcome"] for r in outcomes)),
               "mean_latency_s": statistics.mean(d["latency_s"] for d in complete) if complete else None,
               "mean_writer_latency_s": statistics.mean(r["writer_latency_s"] for r in outcomes) if outcomes else None,
               "token_cost_usd": sum(r["cost_usd"] for r in outcomes),
               "cost_per_report_usd": statistics.mean(r["cost_usd"] for r in outcomes) if outcomes else None,
               "details": details}
    save(path, summary)
    return summary


def private_run() -> dict:
    """Deploy existing app, measure cold wake separately, always stop and reap watchdog."""
    environment(True)
    started = time.monotonic()
    runtime = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
               "conservative_usd_per_wall_second": MODAL_RATE_BOUND,
               "watchdog_deadline_s": MODAL_DEADLINE_S, "budget_usd": 10,
               "app": "stormscore-private-llm", "status": "starting"}
    log = DATA / "modal_lifecycle.log"
    watchdog = subprocess.Popen([sys.executable, str(REPO_ROOT / "tools/modal/task_watchdog.py"),
                                 "--seconds", str(MODAL_DEADLINE_S)],
                                stdout=log.open("w"), stderr=subprocess.STDOUT)
    try:
        with log.open("a") as output:
            deployed = subprocess.run([sys.executable, "-m", "modal", "deploy", "tools/modal/llm_server.py"],
                                      cwd=REPO_ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=600)
        if deployed.returncode:
            raise RuntimeError("Modal deployment failed; inspect local lifecycle log")
        runtime["deployed_at_utc"] = datetime.now(timezone.utc).isoformat()
        before = time.perf_counter()
        models = llm.list_models("modal", live=True)
        runtime["wake_discovery_s"] = time.perf_counter() - before
        runtime["model_available"] = PRIVATE in models
        if not runtime["model_available"]:
            raise RuntimeError("Requested private model not served")
        summary = reports(True)
        runtime["status"] = "complete"
    except Exception as error:
        runtime.update(status="failed", error_type=type(error).__name__,
                       error=str(error) if isinstance(error, (llm.GatewayError, RuntimeError)) else type(error).__name__)
        raise
    finally:
        with log.open("a") as output:
            stopped = subprocess.run([sys.executable, "-m", "modal", "app", "stop",
                                      "stormscore-private-llm", "--yes"],
                                     stdout=output, stderr=subprocess.STDOUT, timeout=120)
        runtime["stop_exit_code"] = stopped.returncode
        runtime["stopped_at_utc"] = datetime.now(timezone.utc).isoformat()
        runtime["wall_time_s_including_deploy_wake_stop"] = time.monotonic() - started
        runtime["runtime_cost_upper_estimate_usd"] = runtime["wall_time_s_including_deploy_wake_stop"] * MODAL_RATE_BOUND
        runtime["cost_note"] = "Conservative wall-time estimate including deployment, startup and stop; not a provider invoice. Modal token cost is zero."
        save(DOCS / "modal_runtime.json", runtime)
        # Normal completion already stopped the app. The watchdog is only a crash safety net.
        watchdog.terminate()
        watchdog.wait(timeout=10)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()
    check_frozen()
    result = private_run() if args.private else reports(False)
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
