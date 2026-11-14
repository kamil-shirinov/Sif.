# CX model gateway and storm reports

Run from `backend` with the project Python:

```sh
~/.venvs/stormscore/bin/python -m pytest -q tests/ai
~/.venvs/stormscore/bin/python -m storm.ai.report --bundle ../contracts/mock_storm.json
~/.venvs/stormscore/bin/python -m storm.ai.smoke
~/.venvs/stormscore/bin/python -m storm.ai.bakeoff --models muse-spark-1.1 muse-spark-1.3
```

Every inference goes through `storm.ai.llm.complete`. All providers use the
deterministic mock unless `live=True` or `LLM_MODE=live`. The explicit `mock`
provider always stays offline. SDK construction is lazy; imports never make
requests. No new dependencies or contract changes are needed.

Live commands are for Kamil's laptop only. The gateway loads environment settings
through python-dotenv at use time, searching upward from the working directory.
In an isolated worktree, configure the environment there or launch with settings
already exported. Credentials and provider responses are never printed by the
gateway. Smoke prints model IDs, timing, and costs. Failed calls additionally
print the finish reason, token usage (including reasoning tokens when available),
and up to 200 characters of assistant message data; HTTP metadata is excluded and
configured API credentials are redacted.

```sh
python -m storm.ai.smoke --live
python -m storm.ai.report --live --bundle ../contracts/mock_storm.json
python -m storm.ai.bakeoff --live --models muse-spark-1.1 muse-spark-1.3
python -m storm.ai.bakeoff --live --models fireworks:accounts/fireworks/models/deepseek-v4.1-flash
```

Meta uses `META_API_KEY`, `META_BASE_URL`, and `META_MODEL`. Fireworks uses
`FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL`, and `FIREWORKS_MODEL_CHECKER`, unless a
model is passed explicitly. Modal support is available through `MODAL_API_KEY`,
`MODAL_BASE_URL`, and `MODAL_MODEL`; smoke skips it when its base URL is absent.
Smoke can select the first discovered model when no default is configured.
It asks for one word with a 1,024-token limit and requests `minimal` reasoning
from Meta or `low` from Fireworks. A provider rejection of `reasoning_effort`
retries without the field, within the gateway's existing three-attempt limit.
These settings follow the [Meta reasoning guide](https://dev.meta.ai/docs/reasoning)
and [Fireworks reasoning guide](https://docs.fireworks.ai/guides/reasoning).
The inspector must use a different model family from the writer, including during
bakeoffs; reports preflight that configuration before the writer request. Numeric
membership alone cannot verify which subject a number describes.

Live inference fails closed without valid provider caps in
`~/.stormscore/caps.json`. Kamil owns this file: the gateway never creates or
changes caps. The existing caps example covers Meta and Fireworks; Modal needs a
cap entry before this gateway will permit inference, plus its own workspace GPU
budget because token estimates cannot account for GPU time. Shared settings files
are unchanged by this lane.

The WAL ledger at `~/.stormscore/ledger.sqlite` reserves worst-case uncached cost
under an immediate SQLite transaction before each request. Parallel processes
share pending reservations. At 75% it warns on stderr; at or above 90% it refuses.
Completed calls reconcile to usage; missing usage, server failures, timeouts, and
interrupted processes retain conservative charges or reservations. Definitively
rejected 4xx attempts release their charge, except uncertain 408 timeouts. Never
clear ledger rows to bypass the guard. Returned gateway costs include any prior
uncertain retry attempts. The SDK's internal retries are disabled; the gateway
allows at most two retries with backoff.

Reports allow 2,048 output tokens and inspector audits allow 1,024, including
reasoning tokens. Each attempt reserves its full current output limit. An empty
answer with `finish_reason="length"` raises a clear reasoning-budget exhaustion
error after accounting for usage; a valid tool-only response remains supported.

The input guard uses UTF-8 byte counts plus framing as a conservative token upper
bound, including tools and assistant tool-call arguments. It rejects estimates
above 60,000 tokens and disallows non-text content whose cost it cannot bound.
Prices match the requested uncached rates; unrecognized IDs use $3/$15 per million
input/output tokens. Version suffixes are not guessed.

`facts_from_bundle` computes move percentage, duration, alarm offsets, ship P&L,
and the final equity difference directly from the bundle. A number passes when it
matches a fact, or that fact rounded at the number's written precision (decimal
half-up). Signs are preserved; numeric words, comma-separated amounts, and k/m/b
scales are checked too. Percentage and basis-point conversions come from explicit
derived facts. Numeric verification does not imply semantic verification.

The radio officer gets one correction attempt with the bad numbers, then uses a
deterministic four-sentence template. The inspector's JSON verdict is retained;
malformed verdicts count as flags. A flagged generated report also switches to the
template and records both the original audit and the template audit. Budget or
provider errors propagate rather than masquerading as a completed live audit.
Mock inspection only certifies the exact deterministic template; it is not a
semantic language model.

The report function returns diagnostic metadata requested by CX. When attaching
it to a schema-version 1 replay bundle, project only the four contract fields
`text`, `verified`, `unverified_numbers`, and `model` into `bundle["report"]`;
retain the inspector and cost metadata separately. This lane does not modify the
bundle contract or the backend exporter's strict validator.

Bakeoff reads local `web/public/bundles/*.json`, skips `index.json`, and never
writes bundles. Use `--bundles PATH` to select another directory. It reports the
first attempt's numeric verification rate, inspector flags (including reports
replaced after a flag), mean end-to-end latency and cost per completed report,
fallback count, and errors. Unprefixed Muse IDs target Meta; Fireworks account
paths and known Fireworks family prefixes target Fireworks. Explicit provider
prefixes work for any ID. Offline runs exercise the same report flow but do not
measure model quality. The tests block network and replace HOME and dotenv loading.
