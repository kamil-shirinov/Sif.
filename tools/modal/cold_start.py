"""Wait for zero runners, then measure an authenticated scale-from-zero start.

Use only after confirming the .env handoff. Only model discovery is requested;
all model interactions go through the gateway. Never prints credentials.
"""

import argparse
from datetime import datetime, timezone
import json
import time

import modal

from storm.ai import llm

from llm_server import APP_NAME


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-seconds", type=int, default=900)
    args = parser.parse_args()
    llm.load_environment()
    function = modal.Function.from_name(APP_NAME, "serve")
    deadline = time.monotonic() + args.wait_seconds
    while True:
        stats = function.get_current_stats()
        if stats.num_total_runners == 0 and stats.backlog == 0:
            break
        if time.monotonic() >= deadline:
            print("Scale-to-zero was not observed; no cold-start result recorded.")
            return 1
        print(f"Waiting for scale-to-zero: runners={stats.num_total_runners}, backlog={stats.backlog}", flush=True)
        time.sleep(30)
    started_utc = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    try:
        models = llm.list_models("modal", live=True)
    except llm.GatewayError as error:
        print(str(error))
        return 1
    print(json.dumps({"cold_start_s": time.perf_counter() - started,
                      "request_started_utc": started_utc,
                      "confirmed_zero_runners_before_request": True, "models": models}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
