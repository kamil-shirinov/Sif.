# Storm report writer bake-off, 14 Nov 2026

This page compares three models as the writer of storm reports. Each model wrote a report
for the same 15 local bundles: 13 SGX storms, the NVDA storm, and the synthetic
`mock_storm`. The bake-off was run with `python -m storm.ai.bakeoff --live`, and every call
went through the budget-guarded gateway.

| Writer | Inspector | Reports done | Errors | First-try verified | Inspector flags | Template fallbacks | Mean latency | Cost / report |
|---|---|---|---|---|---|---|---|---|
| muse-spark-1.3 (Meta) | kimi-k3p1-pro | 15 / 15 | 0 | 93% (14/15) | 0 | 0 | 13.2 s | $0.0156 |
| deepseek-v4p1-flash (Fireworks) | kimi-k3p1-pro | 15 / 15 | 0 | 100% (15/15) | 1 | 1 | 15.6 s | $0.0412* |
| kimi-k3p1-pro (Fireworks) | deepseek-v4p1-flash | 11 / 15 | 4 | 33% (5/15) | 1 | 3 | 20.4 s | $0.0398* |

## How to read the table

- **Inspector.** The inspector always comes from a different model family than the
  writer. The inspector for the Kimi run was set by overriding `FIREWORKS_MODEL_CHECKER`
  for that run only.
- **First-try verified.** The share of all 15 bundles, including failed calls, whose
  first draft passed numeric verification.
- **Inspector flags.** The inspector rejected a generated draft. The report then switched
  to the template.
- **Errors.** All four Kimi errors were reasoning-budget exhaustion. The model used all
  4,096 output tokens on reasoning before producing text, so the gateway raised an error
  and those reports were not written.
- **Inspector flags across rows.** The Kimi run used a different inspector from the other
  two runs, so its flags column is not strictly comparable with theirs.
- **\* Cost.** The gateway's price table lists `kimi-k3.1-pro` and `deepseek-v4.1-flash`,
  but not the Fireworks IDs `kimi-k3p1-pro` and `deepseek-v4p1-flash`. Calls to those two
  are therefore charged at the conservative fallback rate of $3 / $15 per million tokens,
  so their costs are overstated.
- **Facts given to the writers.** The bake-off reads facts with `facts_from_bundle`. It
  does not add the scheduled-event or market-hours facts that `storm.export` adds.

**Result: keep muse-spark-1.3 as the writer.** It was the only model with no errors, no
inspector flags and no fallbacks. It was also the fastest and the cheapest. In the live
export, it wrote 13 of the 14 shipped reports, and the deterministic template wrote the
other one (`eurusd-2026-07-02`). All 14 are verified, and the inspector returned ok on all 14.
