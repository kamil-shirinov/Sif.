# Model choices and live bake-offs, 15 Nov 2026

**Chosen defaults: Qwen 3.8 Max navigator + Kimi inspector; GLM 5.3 reports +
Kimi inspector; GPT-OSS-120B for every private role on one H100.**
All inference used `storm.ai.llm.complete()`, with mock as the offline default,
the existing provider guard and additional task ceilings. No caps, historic
ledger entries, keys, shared dependencies or replay bundles were edited.

## Private crew: same 13 SGX FX bundles

Both rows below use `LLM_PRIVATE_MODE=1`: writer and inspector stay on Modal.
They use identical report-fact fingerprints; mock and NVDA are excluded.

| Private writer / inspector | First draft numbers | Accepted first draft | Fallbacks | Errors | Mean writer / total |
|---|---:|---:|---:|---:|---:|
| modal:Qwen/Qwen3-8B | 10/13 | 5/13 | 8 | 0 | 9.99 / 10.81 s |
| modal:openai/gpt-oss-120b | 13/13 | 11/13 | 0 | 0 | 5.10 / 8.50 s |

First-draft numbers means numeric verification only. Accepted first draft also
requires format acceptance and an ok inspector. GPT-OSS needed two format
corrections, but no template replacement. Its inspector is a separate role
sharing the same weights, not an independent model family. Deterministic code
still checks all numbers. Mean report time includes a single overlapping private
navigator probe; model selection is decided by the higher first-draft numeric
rate before latency. Detailed checks are in
[Qwen private results](../../tools/modal/qwen-private.jsonl) and
[GPT-OSS private results](../../tools/modal/gpt-oss-private.jsonl).

The historical 14 Nov row in `validation.json` was Qwen writer + hosted Kimi:
8/13 first drafts numerically verified, 9 fallbacks, 8.70 s writer / 12.36 s total.
It sent synthetic facts to Fireworks and was **not** an all-private crew run.
It remains preserved separately rather than relabelled as today's baseline.

The matching private navigator stress question passed verified numbers, exact
`stress_test` arguments and an ok private inspector on both models. Qwen took
4.62 s; GPT-OSS took 5.37 s in the isolated repeat (18.93 s while sharing the GPU
with reports). The endpoint rejected unauthenticated `/v1/models` with 401.
GPT-OSS wins the requested first-draft-number criterion, so it is the private
default despite the slightly slower isolated navigator probe.

H100 fit was confirmed live: 65.9651 GiB for model loading, 4.95 GiB available
for KV cache, with a 16,384-token context. Public weights/revision and the image
are pinned in `tools/modal/llm_server.py`. Muse Spark Open is public, but its
smallest official checkpoint is about 537 GB, so it cannot fit one available GPU.
See [Meta checkpoint footprints](https://dev.meta.ai/docs/muse-spark-open/get-the-model)
and [vLLM GPT-OSS serving](https://docs.vllm.ai/projects/recipes/en/latest/OpenAI/GPT-OSS.html).
The first H100 startup stalled before serving. Public tokenizer files are now
fetched and hash-checked in the CPU image build; the successful measured cached
startup was 69.74 s. Failed startup allocation is included in task accounting.

## Navigator: fixed ten-question comparison

[The fixed questions and expected tool arguments](../storm/ai/navigator_bakeoff.py)
cover three symbols, rises/falls, short/long durations, 10x versus 40x leverage,
exposure followed by stress, and two replay shapes. The first comparison exposed
unnecessary tool calls and an omitted no-policy-cuts assumption in stress facts.
The prompt now requests only necessary tools, and that assumption is explicit.
Every model was rerun against the same updated pipeline. The original comparison
is retained in `tools/modal/navigator-baseline-results.json`.

| Navigator | First draft numbers | Final verified | Correct tools | Inspector ok | No-fallback successes | Mean latency | <15 s | Total token cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| meta:muse-spark-1.3 | 8/10 | 10/10 | 10/10 | 10/10 | 6/10 | 31.20 s | 0/10 | $0.195468 |
| meta:muse-wonder-1.0 | 7/10 | 10/10 | 10/10 | 10/10 | 8/10 | 11.60 s | 8/10 | $0.410990 |
| fireworks:accounts/fireworks/models/qwen3p8-max | 7/10 | 10/10 | 10/10 | 10/10 | 8/10 | 7.67 s | 10/10 | $0.133436 |
| fireworks:accounts/fireworks/models/glm-5p3 | 4/10 | 10/10 | 10/10 | 10/10 | 7/10 | 26.40 s | 2/10 | $0.132427 |
| fireworks:accounts/fireworks/models/kimi-k3p1-pro | 4/10 | 10/10 | 10/10 | 10/10 | 5/10 | 15.78 s | 4/10 | $0.144982 |

All rows used Kimi inspection except Kimi's own row, which used GLM. Correct tools
requires every expected call with matching signed move, duration, leverage and
replay ID where specified, and no tool errors. Additional valid calls are allowed.
Final numeric verification alone can include a template. A no-fallback success
requires verified numbers, correct tools, inspector ok and generated prose.
Mean time includes every tool round, correction, inspection and retry; GLM's
113.84 s leverage case is retained rather than trimmed. Costs are totals for ten
questions, including writer and inspector, using uncached rates.

Qwen Max ties Wonder for the most no-fallback successes and is faster and cheaper;
all its questions finished under the demo target. It is the navigator default.
The two remaining Qwen fallbacks are retained in the per-question results; no row
is described as perfect generated-answer reliability. A final live default-route
probe confirmed Qwen writer, Kimi inspector, correct stress arguments and verified
output in 5.13 s. See [full results](../../tools/modal/navigator-results.json).

## Report writer gate: same frozen 15 bundles

These rows use 13 SGX FX bundles, NVDA and the labelled synthetic fixture, with
identical fact fingerprints. Kimi inspected all four writers. Like the previous
bake-off, facts come from `facts_from_bundle`, without the exporter's additional
calendar/market-hours enrichment.

| Report writer | Reports | First draft numbers | Fallbacks | Errors | Inspector flags | Mean total | Cost / report |
|---|---:|---:|---:|---:|---:|---:|---:|
| meta:muse-spark-1.3 | 15/15 | 15/15 | 0 | 0 | 0 | 10.17 s | $0.008667 |
| meta:muse-wonder-1.0 | 15/15 | 15/15 | 0 | 0 | 0 | 6.73 s | $0.016506 |
| fireworks:accounts/fireworks/models/qwen3p8-max | 15/15 | 15/15 | 1 | 0 | 1 | 6.11 s | $0.008448 |
| fireworks:accounts/fireworks/models/glm-5p3 | 15/15 | 15/15 | 0 | 0 | 0 | 4.31 s | $0.004395 |

GLM accepted all 15 first drafts; Spark accepted 14 first drafts and one format
correction. Both had perfect first-draft numeric checks and no flags/fallbacks.
GLM also had lower latency and token cost, so it clears the requested 15-bundle
gate and replaces Spark as report default. The new default was checked live with
verified output and an ok Kimi verdict. Restore Spark using
`REPORT_WRITER_PROVIDER=meta REPORT_WRITER_MODEL=muse-spark-1.3`; navigator selection
is independent. Explicit model/provider calls still take precedence.

## Validation, shutdown and task spend

Backend: **293 passed, 6 skipped**. Private/gateway/AI regressions are also run
separately. Skips are conditional data/live prerequisites in the isolated worktree.
Both the 13-report private rows, private navigator checks, two complete five-model
navigator comparisons, four 15-report rows and selected-default live probes ran.

The private function was observed at zero runners and zero backlog after idle.
The final source (including explicit CPU/RAM limits) was deployed, then the app
was stopped. `tools/modal/final-app-state.json` confirms both task app IDs stopped
with zero tasks. Defaults remain min=0, max=1 and a 300 s idle window.
**Wake it three to five minutes before judging**: redeploy, set `--warm`, and run
an authenticated smoke request. Commands and the post-judging stop procedure are
in [the private endpoint README](../../tools/modal/README.md#judging-warmth).
Keep the existing URL and Secret; no new credential handoff is needed.

| Provider | This task | Ceiling |
|---|---:|---:|
| Meta | $1.481810 uncached token accounting | $20 |
| Fireworks | $1.241302 uncached token accounting | $20 |
| Modal | $8.374 conservative configured-resource wall-time estimate | $25 |

Meta/Fireworks totals come from normal task-prefixed reservations, including
uncertain attempts, through the budget API. They are not billing invoices and
ignore cache discounts. The existing 75% warning / 90% refusal remains intact;
task limits apply the same thresholds atomically. Modal tokens are ledgered at
zero because Modal bills runtime. Its estimate assumes continuous one-container
allocation at $0.002/s across the entire task window, including baseline, failed
startup, image builds and idle/stopped periods; it is not measured dollar spend.
[Modal resource pricing](https://modal.com/pricing) supports the resource-rate
assumptions. The supported metrics API observed 27.19 H100 minutes for the second
app, but has missing buckets and omits the stopped first app; it is not presented
as complete task billing. The stopped-app object lookup API was unavailable.
See [task spend](../../tools/modal/task-spend.json) and
[partial allocation metrics](../../tools/modal/task-gpu-usage.json).

New model prices were checked against
[Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits) and
[Fireworks pricing](https://docs.fireworks.ai/serverless/pricing).
The historical table below retains its original accounting; today's rows use the
correct model aliases in `storm.ai.prices`.

---

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
