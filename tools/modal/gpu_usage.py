"""Report allocated GPU minutes from Modal metrics, including startup/idle time.

No model request, credentials, env file or token ledger is read by this tool.
Modal rounds the time window to complete metric buckets; the output states the
effective bounds and missing observations instead of inventing unreported usage.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import math

import modal

from llm_server import APP_NAME


def summarize(metrics):
    width_minutes = metrics.bucket_size.total_seconds() / 60
    totals = {}
    missing = {}
    for name, series in metrics.series.items():
        if not name.startswith("gpu_count_") or not name.endswith("_avg"):
            continue
        values = [point.value for point in series.points]
        valid = [value for value in values if value is not None and math.isfinite(value)]
        totals[name] = sum(valid) * width_minutes
        expected = round((metrics.until - metrics.since) / metrics.bucket_size)
        missing[name] = max(expected, len(values)) - len(valid)
    return {
        "since_utc": metrics.since.isoformat(), "until_utc": metrics.until.isoformat(),
        "bucket_seconds": metrics.bucket_size.total_seconds(),
        "allocated_gpu_minutes_observed": totals,
        "missing_buckets": missing,
        "note": "Allocated GPU count integrated over complete Modal metric buckets; missing buckets are unknown.",
    }


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("Provide an explicit UTC offset or Z")
    return parsed.astimezone(timezone.utc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=utc, required=True)
    parser.add_argument("--until", type=utc, default=datetime.now(timezone.utc))
    args = parser.parse_args()
    function = modal.Function.from_name(APP_NAME, "serve")
    metrics = function.metrics.export(since=args.since, until=args.until,
                                     bucket_size=timedelta(minutes=1), groups=["gpu"])
    print(json.dumps(summarize(metrics), sort_keys=True))


if __name__ == "__main__":
    main()
