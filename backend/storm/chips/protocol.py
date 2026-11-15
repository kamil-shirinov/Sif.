"""Immutable registration, safe JSON and source integrity checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from storm.backtest import code_fingerprint
from storm.paths import REPO_ROOT

DOCS = REPO_ROOT / "docs/chips"
DATA = REPO_ROOT / "data/processed/chips"
REGISTRATION = DOCS / "preregistration.md"
MAIN = Path("/Users/kamilshirinov/Desktop/stormscore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def json_default(value):
    if value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False, default=json_default) + "\n")


def registration() -> dict:
    return json.loads(REGISTRATION.read_text().split("```json\n", 1)[1].split("\n```", 1)[0])


def registration_commit() -> str:
    return subprocess.check_output(["git", "log", "--diff-filter=A", "--format=%H", "--",
                                    str(REGISTRATION)], cwd=REPO_ROOT, text=True).strip()


def check_registration() -> dict:
    spec = registration()
    assert hashlib.sha256(canonical(spec["config"]).encode()).hexdigest() == spec["config_sha256"]
    commit = registration_commit()
    if not commit:
        raise ValueError("Commit preregistration before acquisition")
    original = subprocess.check_output(["git", "show", f"{commit}:docs/chips/preregistration.md"],
                                       cwd=REPO_ROOT)
    if hashlib.sha256(original).hexdigest() != sha256(REGISTRATION):
        raise ValueError("Preregistration changed after commit")
    return spec


def check_frozen() -> dict:
    spec = check_registration()
    if code_fingerprint() != spec["code_fingerprint"]:
        raise ValueError("Frozen core fingerprint mismatch")
    for name, expected in spec["source_sha256"].items():
        if sha256(REPO_ROOT / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")
    return spec
