"""Immutable protocol, input inventory, and deterministic random streams."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from storm.backtest import calendar_fingerprint, code_fingerprint
from storm.detector import load_calendar
from storm.paths import REPO_ROOT

DOCS = REPO_ROOT / "docs/stats"
REGISTRATION = DOCS / "preregistration.md"
MAIN = Path("/Users/kamilshirinov/Desktop/stormscore")
PYTHON = Path("/Users/kamilshirinov/.venvs/stormscore/bin/python")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def registration() -> dict:
    return json.loads(REGISTRATION.read_text().split("```json\n", 1)[1].split("\n```", 1)[0])


def check_frozen() -> dict:
    spec = registration()
    commit = subprocess.check_output(
        ["git", "log", "--diff-filter=A", "--format=%H", "--", "docs/stats/preregistration.md"],
        cwd=REPO_ROOT, text=True).strip()
    original = subprocess.check_output(["git", "show", commit + ":docs/stats/preregistration.md"], cwd=REPO_ROOT)
    if hashlib.sha256(original).hexdigest() != sha256(REGISTRATION):
        raise ValueError("Statistical registration changed after commit")
    if hashlib.sha256(canonical(spec["config"]).encode()).hexdigest() != spec["config_sha256"]:
        raise ValueError("Configuration hash differs")
    if code_fingerprint() != spec["code_fingerprint"]:
        raise ValueError("Frozen main calculation fingerprint differs")
    if calendar_fingerprint(load_calendar()) != spec["calendar_content_sha256"]:
        raise ValueError("Calendar differs")
    for name, expected in spec["source_sha256"].items():
        if sha256(REPO_ROOT / name) != expected:
            raise ValueError("Frozen source differs: " + name)
    for name, expected in spec["input_documents_sha256"].items():
        if sha256(REPO_ROOT / name) != expected:
            raise ValueError("Registered input document differs: " + name)
    for name, expected in (("metrics.json", spec["sgx_metrics_sha256"]),
                           ("detector_config.json", spec["source_config_file_sha256"])):
        if sha256(MAIN / "data/processed" / name) != expected:
            raise ValueError("Registered SGX input differs: " + name)
    return {**spec, "registration_commit": commit}


def rng_for(*keys, seed: int = 20261115):
    # Stable per task/dataset keys: adding round two cannot change earlier draws.
    digest = hashlib.sha256("/".join(map(str, keys)).encode()).digest()
    return np.random.default_rng(np.random.SeedSequence([seed, *np.frombuffer(digest, dtype="<u4").tolist()]))


def json_default(value):
    if value is pd.NaT:
        return None
    if isinstance(value, (Path, pd.Timestamp)):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=json_default) + "\n")


def worktrees() -> dict[str, Path]:
    records = subprocess.check_output(["git", "worktree", "list", "--porcelain"], cwd=REPO_ROOT, text=True)
    found = {}
    for record in records.split("\n\n"):
        fields = dict(line.split(" ", 1) for line in record.splitlines() if " " in line)
        if "branch" in fields:
            found[fields["branch"].removeprefix("refs/heads/")] = Path(fields["worktree"])
    return found
