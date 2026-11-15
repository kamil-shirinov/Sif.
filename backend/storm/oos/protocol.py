"""Read the immutable registration and check the core without modifying it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from storm.backtest import calendar_fingerprint, code_fingerprint
from storm.detector import load_calendar
from storm.paths import REPO_ROOT

DOCS = REPO_ROOT / "docs" / "oos"
REGISTRATION = DOCS / "preregistration.md"
DATA = REPO_ROOT / "data" / "external"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def registration() -> dict:
    return json.loads(REGISTRATION.read_text().split("```json\n", 1)[1].split("\n```", 1)[0])


def registration_commit() -> str:
    return subprocess.check_output(
        ["git", "log", "--diff-filter=A", "--format=%H", "--", str(REGISTRATION)],
        cwd=REPO_ROOT, text=True,
    ).strip()


def check_registration() -> dict:
    """Validate the immutable protocol without requiring today's core to be frozen."""
    spec = registration()
    if hashlib.sha256(canonical(spec["config"]).encode()).hexdigest() != spec["config_sha256"]:
        raise ValueError("config hash mismatch")
    commit = registration_commit()
    if not commit:
        raise ValueError("preregistration must be committed first")
    original = subprocess.check_output(
        ["git", "show", f"{commit}:docs/oos/preregistration.md"], cwd=REPO_ROOT,
    )
    if hashlib.sha256(original).hexdigest() != sha256(REGISTRATION):
        raise ValueError("preregistration was edited after its first commit")
    return spec


def check_frozen() -> dict:
    """Primary runs still refuse drift; historical verification rebuilds the old core."""
    spec = check_registration()
    checks = [
        (code_fingerprint() == spec["code_fingerprint"], "frozen core code fingerprint mismatch"),
        (calendar_fingerprint(load_calendar()) == spec["calendar_content_sha256"], "frozen calendar mismatch"),
        (sha256(REPO_ROOT / "docs" / "metrics.md") == spec["metrics_document_sha256"], "frozen metrics definitions mismatch"),
    ]
    for ok, reason in checks:
        if not ok:
            raise ValueError(reason)
    return spec
