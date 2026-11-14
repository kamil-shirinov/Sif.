# StormScore private GPU crew

`llm_server.py` serves public Apache-2.0 `Qwen/Qwen3-8B` weights at a pinned revision,
using vLLM 0.10.2 on **one L4 (24 GB)**. BF16 weights, a 16,384-token context, one
generation sequence, and eager execution leave room for the KV cache without a
larger GPU. This is the initial configuration; deployment alone does not prove
the model fits or measure inference quality. Validate after the env handoff.
`MODAL_GPU=A10G` selects another 24 GB GPU if L4 capacity is unavailable;
`MODAL_GPU=L40S` is an explicit 48 GB fallback if later measurements require it.
There is no automatic GPU upgrade or multi-GPU allocation.

The 14 November 2026 deployment uses `MODAL_GPU=L40S`: Modal reported unavailable
L4 and A10G capacity. Reproduce that deployment with the same variable; plain
`modal deploy` returns to the default L4 configuration. Recorded smoke, privacy,
quality, cold-start and allocation results are in [validation.json](validation.json).
The configured idle window is 300 seconds; this run observed zero runners about
6.5 minutes after the final external request, including platform shutdown and
30-second observer polling. Treat the setting as an autoscaler policy, not an
exact wall-clock shutdown guarantee.

The Hugging Face cache is on the `stormscore-qwen3-weights` Modal Volume. The
container receives only the `stormscore-private-llm` Secret, containing
`MODAL_API_KEY`. vLLM enforces `--api-key` on its `/v1` inference routes. Request
and access logging and usage telemetry are disabled; startup logs are redacted
because vLLM may print parsed arguments. No `.env`, trader book, or backend source
is uploaded with the image. Modal remains the infrastructure operator.

Defaults: `min_containers=0`, `max_containers=1`, `buffer_containers=0`,
`scaledown_window=300`. GPU idle time during that window is billable. Workspace
usage/spending limits are managed by Kamil and never changed by these tools.
An unauthenticated request can wake a container before vLLM rejects it; this
endpoint is key-protected, not a network-private service.

## Deploy and handoff

From this worktree, using Kamil's Modal-authenticated environment:

```sh
~/.venvs/stormscore/bin/python tools/modal/provision_secret.py
~/.venvs/stormscore/bin/python -m modal deploy tools/modal/llm_server.py
```

The provisioning tool creates a random key, stores it in Modal Secrets, and
prints only the path of a mode-0600 handoff file inside a mode-0700 temporary
directory outside the repository. An existing named Secret is left unchanged.
Never cat the file into a terminal captured by an agent, paste it into chat, or
commit it. Kamil can copy it locally with `pbcopy < /path/printed/by/the/tool` and
paste it into `.env`. The two lines to add manually are:

```dotenv
MODAL_BASE_URL=https://<deployment-url>/v1
MODAL_API_KEY=<paste the key from the private local handoff>
```

No `MODAL_MODEL` setting is needed. Delete the temporary credential file after
the handoff. The tools never edit `.env`. `modal==1.6.4` is a deployment-only
dependency, recorded in this directory. Existing navigator API tests also need
FastAPI (missing from shared `backend/requirements.txt`; Kamil must add it there).
The requested local venv is Python 3.10; Modal warns that SDK 1.7 will require a
newer Python, so the deploy tooling is pinned to 1.6.4.

## Run the whole crew privately

Set `LLM_PRIVATE_MODE=1` on the backend process. Every live model role, including
the navigator and inspector, routes to Modal, regardless of external provider
defaults. No external model fallback is allowed. Mock remains the default until
explicit live opt-in. The inspector is a separate role sharing Qwen weights in
this mode, not a second model family. Code still verifies every report number.

```sh
cd backend
STORM_ENV_FILE=~/Desktop/stormscore/.env LLM_PRIVATE_MODE=1 \
  ~/.venvs/stormscore/bin/python -m storm.ai.smoke --live
```

The gateway sends `MODAL_API_KEY` as a bearer credential, disables Qwen thinking
per request, and allows 600 seconds for a cold start. Token ledger entries are
zero dollars for Modal, including retries: Modal bills runtime separately. This
does not mean the GPU is free. Caps and existing ledger entries are untouched.

## Judging warmth

Keep one container warm on the deployed function, then restore scale-to-zero:

```sh
~/.venvs/stormscore/bin/python -m modal run tools/modal/llm_server.py --warm
~/.venvs/stormscore/bin/python -m modal run tools/modal/llm_server.py --no-warm
```

Alternatively deploy with `MODAL_KEEP_WARM=1` for one warm container; redeploy
without it to restore the default. Warm judging accrues GPU runtime continuously.

## Validation after Kamil confirms the env handoff

```sh
cd backend
~/.venvs/stormscore/bin/python -m pytest -q tests/ai ../tools/modal/test_private.py
STORM_ENV_FILE=~/Desktop/stormscore/.env \
  ~/.venvs/stormscore/bin/python -m storm.ai.smoke --live --provider modal
STORM_ENV_FILE=~/Desktop/stormscore/.env LLM_PRIVATE_MODE=0 \
  ~/.venvs/stormscore/bin/python -m storm.ai.bakeoff --live \
  --models modal:Qwen/Qwen3-8B --fx-only --expected-bundles 13 --details \
  --bundles ~/Desktop/stormscore/web/public/bundles
```

For that bake-off, `FIREWORKS_MODEL_CHECKER` must be Kimi. It sends only the
labelled synthetic book facts to Fireworks for comparison; it is **not private
mode**. The output records the inspector model, first-try numeric verification
rate, fallback count, mean writer latency and mean end-to-end latency including
Kimi. Offline bake-offs test the pipeline and do not measure model quality.
First-try verification counts numbers only; it can pass before a format failure
or an inspector rejection. Detailed runs also partition all reports into accepted
first attempts, accepted retries, number-check fallbacks, format fallbacks and
inspector fallbacks, and retain audit issues. The original `validation.json` saved
only aggregates, so its exact historical partition cannot be recovered.

[review_bakeoff.json](review_bakeoff.json) retains the review repeat's per-replay
checks, audit issues and exclusive outcomes. It also recovers the original
acceptance/retry counts from read-only completed-call metadata. Original terminal
number-versus-format causes remain unknown; they are not replaced with the repeat's
results. Initial numeric success is kept separate from final prose acceptance.

For a cold-start measurement, first confirm `serve.get_current_stats()` reports
zero runners after the 300-second idle window, then time authenticated model
discovery through `storm.ai.llm.list_models('modal', live=True)`. Report the
scale-from-zero time separately from warm inference latency and the first-ever
weight-download startup. Include the idle tail and every failed startup in GPU
runtime; use Modal runtime/billing metrics, or label sampled runner-time estimates
and their sampling interval explicitly. Deployment/image-build time is not GPU
inference time. Do not infer GPU minutes from report latency alone.

To wait for observed scale-to-zero and time the next authenticated model discovery:

```sh
PYTHONPATH=backend STORM_ENV_FILE=~/Desktop/stormscore/.env \
  ~/.venvs/stormscore/bin/python -u tools/modal/cold_start.py
```

After the final idle tail has scaled down and metric ingestion has caught up:

```sh
~/.venvs/stormscore/bin/python tools/modal/gpu_usage.py \
  --since 2026-11-14T19:06:00Z --until <end-time-in-UTC>
```

This integrates Modal's allocated GPU count over complete one-minute buckets,
reports the effective UTC bounds and counts missing observations. Unknown
buckets are not silently called zero. It includes all startup attempts and idle
time in the selected window; it is an allocation measurement, not a dollar bill.

References: [Modal web servers](https://modal.com/docs/reference/modal.web_server),
[autoscaling](https://modal.com/docs/guide/scale),
[vLLM server flags](https://docs.vllm.ai/en/v0.10.2/cli/serve.html),
[Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B).
