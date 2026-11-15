"""Render benchmark tables directly from saved gateway evaluation results."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def row_file(name):
    return json.loads((HERE / name).read_text().splitlines()[-1])


def private_table():
    lines = ["| Private writer / inspector | First draft numbers | Accepted first draft | Fallbacks | Errors | Mean writer / total |",
             "|---|---:|---:|---:|---:|---:|"]
    for name in ("qwen-private.jsonl", "gpt-oss-private.jsonl"):
        r = row_file(name)
        n = r["reports"] + r["errors"]
        first = round(r["first_try_verification_rate"] * n)
        accepted = r["outcome_counts"].get("passed_first_try", 0)
        lines.append(f"| {r['model']} | {first}/{n} | {accepted}/{n} | {r['fallbacks']} | {r['errors']} | "
                     f"{r['mean_writer_latency_s']:.2f} / {r['mean_latency_s']:.2f} s |")
    return "\n".join(lines)


def navigator_table():
    rows = json.loads((HERE / "navigator-results.json").read_text())["models"]
    lines = ["| Navigator | First draft numbers | Final verified | Correct tools | Inspector ok | No-fallback successes | Mean latency | <15 s | Total token cost |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        n = r["questions"]
        lines.append(f"| {r['model']} | {r['first_try_verified']}/{n} | {r['verified']}/{n} | "
                     f"{r['correct_tool_use']}/{n} | {r['inspector_ok']}/{n} | {r['success']}/{n} | "
                     f"{r['mean_latency_s']:.2f} s | {r['under_15_s']}/{n} | ${r['cost_usd']:.6f} |")
    return "\n".join(lines)


def report_table():
    lines = ["| Report writer | Reports | First draft numbers | Fallbacks | Errors | Inspector flags | Mean total | Cost / report |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name in ("spark-reports.jsonl", "wonder-reports.jsonl", "qwen-max-reports.jsonl", "glm-reports.jsonl"):
        if not (HERE / name).exists():
            continue
        r = row_file(name)
        n = r["reports"] + r["errors"]
        lines.append(f"| {r['model']} | {r['reports']}/{n} | {round(r['first_try_verification_rate'] * n)}/{n} | "
                     f"{r['fallbacks']} | {r['errors']} | {r['inspector_flags']} | {r['mean_latency_s']:.2f} s | "
                     f"${r['cost_per_report_usd']:.6f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(private_table(), navigator_table(), report_table(), sep="\n\n")
