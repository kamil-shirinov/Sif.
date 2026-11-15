"""Immutable registration 2 and its independent acquisition root."""
import hashlib
import json
import platform
import subprocess

import numpy
import pandas
import pyarrow

from storm.backtest import calendar_fingerprint, code_fingerprint
from storm.detector import load_calendar
from .protocol import DATA, DOCS, REPO_ROOT, canonical, sha256

REGISTRATION2 = DOCS / "preregistration-2.md"
DATA2 = DATA / "round2"


def registration2():
    return json.loads(REGISTRATION2.read_text().split("```json\n", 1)[1].split("\n```", 1)[0])


def runtime():
    return {"implementation": platform.python_implementation(), "python": platform.python_version(),
            "numpy": numpy.__version__, "pandas": pandas.__version__, "pyarrow": pyarrow.__version__}


def registration2_commit():
    return subprocess.check_output(["git", "log", "--diff-filter=A", "--format=%H", "--",
                                    str(REGISTRATION2)], cwd=REPO_ROOT, text=True).strip()


def check_registration2():
    spec = registration2()
    if hashlib.sha256(canonical(spec["config"]).encode()).hexdigest() != spec["config_sha256"]:
        raise ValueError("registration 2 config hash mismatch")
    commit = registration2_commit()
    if not commit:
        raise ValueError("registration 2 must be committed before acquisition")
    original = subprocess.check_output(["git", "show", commit + ":docs/oos/preregistration-2.md"], cwd=REPO_ROOT)
    if hashlib.sha256(original).hexdigest() != sha256(REGISTRATION2):
        raise ValueError("registration 2 changed after its first commit")
    return spec


def check_frozen2():
    spec = check_registration2()
    if runtime() != spec["runtime"]:
        raise ValueError(f"registration 2 requires runtime {spec['runtime']}; running {runtime()}")
    if code_fingerprint() != spec["code_fingerprint"]:
        raise ValueError("registration 2 core fingerprint mismatch")
    if calendar_fingerprint(load_calendar()) != spec["calendar_content_sha256"]:
        raise ValueError("registration 2 calendar mismatch")
    if sha256(REPO_ROOT / "docs/metrics.md") != spec["metrics_document_sha256"]:
        raise ValueError("registration 2 metric definitions mismatch")
    return spec
