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
requests. The gateway and reports need no new dependencies; navigator integration
requirements are listed below.

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

Report and navigator writers allow 4,096 output tokens and inspector audits allow
2,048, including reasoning tokens. All request `reasoning_effort="low"`; a provider
rejection retries without that field through the gateway. Each attempt reserves
its full current output limit, including correction and compatibility retries. An empty
answer with `finish_reason="length"` raises a clear reasoning-budget exhaustion
error after accounting for usage; a valid tool-only response remains supported.

Every ledger connection sets a 30-second SQLite busy timeout before setup or
transactions. Concurrent WAL initialization also retries lock errors within that
limit, since journal-mode negotiation may bypass SQLite's busy handler. Cap checks
and reservations remain atomic inside `BEGIN IMMEDIATE`.

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

## Navigator

`ask(question, storm_id=None, live=False)` in `storm.ai.navigator` calls the
registered deterministic tools through `llm.complete` (Meta in live mode). The
response has exactly `answer`, `verified`, `unverified_numbers`, `tool_calls`,
`inspector`, and `scenario`. Each recorded call includes its ID, name, arguments,
and result. Only actual tool results authorize numbers; requested arguments do
not. The complete scenario bundle is returned separately; compact derived facts
are sent to the model. There are at most four tool rounds, with four calls per
round. Prose gets one correction attempt, then a deterministic template. The
independent inspector audits the final answer; flagged generated prose is replaced
with the template and audited again. Mock auditing certifies only that template.
`verified` means numeric verification, independently of the inspector verdict or
tool execution success; failed calls retain an `error` result.

```sh
cd backend
python -m pytest -q tests/ai
python -m storm.ai.navigator "what if USDJPY drops 3% in 30 minutes?" --storm usdjpy-2026-07-30
```

The CLI writes a scenario JSON to `web/public/bundles` (override with `--out`).
It exits unsuccessfully for tool errors. First export the real base bundle with
`storm.export`; missing SGX data is an explicit error, never replaced with mock
prices. For an entirely offline smoke using the labelled synthetic fixture:

```sh
LLM_MODE=mock python -m storm.ai.navigator "what if USDJPY drops 3% in 30 minutes?" \
  --storm mock_storm --bundles ../contracts --out ../work/navigator-bundles
```

Scenario prices resample cumulative onset-to-trough log returns and scale them by
`log1p(move_pct / 100) / log(base_trough / base_onset)`. The replay starts at onset,
ends at the resized trough, and checks the rounded final price against the target
within a basis point. Both ships, their cuts, liquidations and exposure snapshot
are recomputed with the existing `storm.exposure` functions. The synthetic book
uses the exporter's default long-USD notional and equity; it is not a custom trader
book. OHLC envelopes use consecutive scenario mids. Alarm timing and sea conditions
are resampled assumptions from the base, not a rerun or forecast from the detector.
The title identifies a synthetic shape when a test fixture is used. Endpoint
stress uses `storm.exposure.stress_test` before liquidation; its P&L can differ
from final scenario equity because the latter includes policy cuts and liquidation.
All calculations mark at mid with no spread or slippage, matching the simulator.

The backend owner can mount `storm.ai.navigator_api.router` with
`app.include_router(router)`. `POST /api/navigator/ask` accepts
`{"question": "...", "storm_id": "..."}` (storm_id optional) and returns the
six fields above, including `scenario: null` for non-scenario answers. Live mode
is configured on the server, never selected by a request field. Validation errors
return 422, provider errors 502, and unavailable budgets 503. Synchronous routes
run in FastAPI's threadpool.

Integration requirements for Kamil (shared files are not changed in this lane):

- Add **`fastapi>=0.115`** to `backend/requirements.txt`; the router also uses its
  Pydantic dependency. API tests use `httpx` (already supplied with compatible
  OpenAI installations; install separately if needed). FastAPI was already
  installed in this development environment.
- CC-L must add `source: "scenario"` to `storm.validate` and the replay contract.
  Until that shared change lands, `validate_shape` passes a copy with
  `source: "synthetic"` to the existing validator, preserving every other field.
  The returned and written bundle retains `source: "scenario"`; tests assert it
  separately. Direct `python -m storm.validate` on that file will reject the source
  until CC-L's enum extension lands. No shared files or validator globals change.
- Mount the router in the live backend application. No app or `contracts/api.md`
  exists on the main revision used for this lane, so the request/response shape
  follows the live-task contract supplied in the navigator assignment.
