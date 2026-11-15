"""Stop the single-GPU app at a conservative task wall-time ceiling.

Run alongside experiments; interrupting this process also stops the app. The
default two-hour bound at $0.002/second is $14.40, below 75% of the $25 ceiling,
including one H100, four CPUs, 16 GiB RAM and margin. This is an upper bound,
not a billing measurement. Never changes workspace caps or the token ledger.
"""
import argparse
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=7200)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 7200:
        parser.error("Use at most two hours")
    deadline = time.monotonic() + args.seconds
    print(f"Modal watchdog active: maximum {args.seconds} seconds", flush=True)
    try:
        while time.monotonic() < deadline:
            time.sleep(min(5, max(0, deadline - time.monotonic())))
    finally:
        subprocess.run([sys.executable, "-m", "modal", "app", "stop",
                        "stormscore-private-llm", "--yes"], check=True)


if __name__ == "__main__":
    main()
