"""StormScore's private OpenAI-compatible endpoint. Deploy with modal deploy.

One GPU, pinned public weights, authenticated inference, no prompt logs.
MODAL_KEEP_WARM=1 keeps the sole container warm for judging (billed while idle).
"""

import os

import modal

APP_NAME = "stormscore-private-llm"
SECRET_NAME = "stormscore-private-llm"
MODEL = os.getenv("PRIVATE_MODEL", "openai/gpt-oss-120b")
REVISIONS = {
    "Qwen/Qwen3-8B": "c4991a667c9137cff07024144d448d2afe76abc4",
    "openai/gpt-oss-120b": "b5c939de8f754692c1647ca79fbf85e8c1e70f8a",
}
REVISION = REVISIONS[MODEL]
PORT = 8000
KEEP_WARM = os.getenv("MODAL_KEEP_WARM", "0") == "1"
GPU = os.getenv("MODAL_GPU", "H100" if MODEL.startswith("openai/") else "L40S")
if GPU not in {"L4", "A10G", "L40S", "H100", "H200", "B200"}:
    raise ValueError("Unsupported single GPU")

app = modal.App(APP_NAME)
weights = modal.Volume.from_name("stormscore-qwen3-weights", create_if_missing=True)
image = (
    modal.Image.from_registry("vllm/vllm-openai:v0.11.0", add_python="3.12")
    .entrypoint([])
    .env({
        "HF_HOME": "/weights",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "VLLM_NO_USAGE_STATS": "1",
    })
    .add_local_file(__file__, remote_path="/root/llm_server.py", copy=True)
)


@app.function(
    image=image,
    gpu=GPU,
    cpu=4,
    memory=16384,
    volumes={"/weights": weights},
    secrets=[modal.Secret.from_name(SECRET_NAME, required_keys=["MODAL_API_KEY"])],
    min_containers=int(KEEP_WARM),
    max_containers=1,
    buffer_containers=0,
    scaledown_window=300,
    timeout=900,
    startup_timeout=900,
    include_source=False,
)
@modal.concurrent(max_inputs=8)
@modal.web_server(PORT, startup_timeout=900)
def serve():
    import subprocess
    import threading

    key = os.environ["MODAL_API_KEY"]
    if not key.strip():
        raise RuntimeError("Modal Secret must contain a nonempty MODAL_API_KEY")
    command = [
        "vllm", "serve", MODEL,
        "--revision", REVISION,
        "--served-model-name", MODEL,
        "--host", "0.0.0.0", "--port", str(PORT),
        "--api-key", key,
        "--dtype", "bfloat16",
        "--max-model-len", "16384",
        "--max-num-seqs", "1",
        "--max-num-batched-tokens", "2048",
        "--gpu-memory-utilization", "0.90",
        "--enforce-eager",
        "--enable-auto-tool-choice", "--tool-call-parser", "openai" if MODEL.startswith("openai/") else "hermes",
        "--reasoning-parser", "openai_gptoss" if MODEL.startswith("openai/") else "qwen3",
        "--disable-log-requests", "--disable-uvicorn-access-log",
        "--uvicorn-log-level", "warning",
    ]
    # vLLM startup can render its parsed arguments (including --api-key).
    # Never print argv; redact the combined child stream before Modal receives it.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)

    def forward_logs():
        for line in process.stdout:
            print(line.replace(key, "[redacted]"), end="", flush=True)

    threading.Thread(target=forward_logs, daemon=True).start()


@app.local_entrypoint()
def autoscale(warm: bool = False):
    """Toggle judging warmth on the deployed function without rebuilding."""
    deployed = modal.Function.from_name(APP_NAME, "serve")
    deployed.update_autoscaler(min_containers=int(warm), max_containers=1,
                               buffer_containers=0, scaledown_window=300)
    print(f"Judging warm container: {warm}; maximum: 1; idle window: 300 seconds")
