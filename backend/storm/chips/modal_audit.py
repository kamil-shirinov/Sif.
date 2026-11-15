"""Read allocation and stop evidence by app ID after the deployment is stopped."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import math
import subprocess
import sys

from .protocol import DOCS, save


def audit() -> dict:
    import modal
    from modal.client import _Client
    from modal_proto import api_pb2

    runtime = json.loads((DOCS / "modal_runtime.json").read_text())
    proc = subprocess.run([sys.executable, "-m", "modal", "app", "list", "--json"],
                          capture_output=True, text=True, timeout=60, check=True)
    apps = [app for app in json.loads(proc.stdout) if app.get("description") == runtime["app"]]
    started = datetime.fromisoformat(runtime["started_at_utc"])
    matching = [app for app in apps if datetime.fromisoformat(app["created_at"]) >= started]
    if len(matching) != 1:
        raise ValueError("Cannot uniquely identify the task's Modal app")
    app = matching[0]
    assert app["state"] == "stopped" and app["tasks"] == "0"
    save(DOCS / "modal_final_state.json", {"app": app, "stopped": True, "running_tasks": 0})
    stopped = datetime.fromisoformat(app["stopped_at"])
    runtime.update(server_stopped_at_utc=stopped.isoformat(), observed_running_tasks=0,
                   observed_final_state=app["state"],
                   conservative_billing_window_s=(stopped - started).total_seconds(),
                   runtime_cost_upper_estimate_usd=(stopped - started).total_seconds() * runtime["conservative_usd_per_wall_second"])
    save(DOCS / "modal_runtime.json", runtime)

    async def function_id():
        # Same metadata RPC as Modal's own runner. It does not invoke the app.
        client = await _Client.from_env()
        response = await client._stub.AppGetLayout(api_pb2.AppGetLayoutRequest(app_id=app["app_id"]))
        return response.app_layout.function_ids["serve"]

    try:
        fid = asyncio.run(function_id())
        function = modal.Function.from_id(fid)
        # Export complete buckets through termination; the app had no allocation
        # before creation or after this confirmed stop, including rounded edges.
        bucket_end = stopped.replace(second=0, microsecond=0) + timedelta(minutes=1)
        metrics = function.metrics.export(since=started, until=bucket_end,
                                          bucket_size=timedelta(minutes=1), groups=["gpu"])
        width = metrics.bucket_size.total_seconds() / 60
        expected = round((metrics.until - metrics.since) / metrics.bucket_size)
        totals, missing = {}, {}
        for name, series in metrics.series.items():
            if name.startswith("gpu_count_") and name.endswith("_avg"):
                valid = [point.value for point in series.points if point.value is not None and math.isfinite(point.value)]
                totals[name] = sum(valid) * width
                missing[name] = max(expected, len(series.points)) - len(valid)
        result = {"status": "retrieved", "function_id": fid,
                  "task_started_at_utc": started.isoformat(), "server_stopped_at_utc": stopped.isoformat(),
                  "since_utc": metrics.since.isoformat(), "until_utc": metrics.until.isoformat(),
                  "bucket_seconds": metrics.bucket_size.total_seconds(),
                  "allocated_gpu_minutes_observed": totals, "missing_buckets": missing,
                  "note": "Allocated GPU count integrated over returned complete buckets; uncovered time and missing buckets are unknown. No GPU was woken to retrieve metrics."}
    except Exception as error:
        result = {"status": "unavailable", "error_type": type(error).__name__,
                  "note": "Stopped-app allocation lookup unavailable; use the separately labelled conservative billing-window estimate. No GPU was woken."}
    save(DOCS / "modal_gpu_usage.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
