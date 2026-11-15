"""Check the registered core in a disposable checkout, independent of today's main."""
from __future__ import annotations

from contextlib import contextmanager
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from .protocol import DOCS, REPO_ROOT, check_registration, registration_commit, sha256

AMENDMENT = DOCS / "amendment-2026-11-15-historical-runtime.md"


def registered_runtime() -> dict[str, str]:
    return json.loads(AMENDMENT.read_text().split("```json\n", 1)[1].split("\n```", 1)[0])


def runtime_mismatches() -> list[str]:
    running = {"implementation": platform.python_implementation(), "python": platform.python_version(),
               **{name: importlib.metadata.version(name) for name in ("numpy", "pandas", "pyarrow")}}
    return [f"{name}: registered {value}, running {running[name]}"
            for name, value in registered_runtime().items() if running[name] != value]


def git(root: Path, *args: str) -> bytes:
    # Read local objects, or change only the disposable clone. Never fetch or
    # register a worktree in the caller's shared Git metadata.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.check_output(["git", "-C", str(root), *args], env=env, stderr=subprocess.PIPE)


@contextmanager
def frozen_checkout():
    """Restore base_commit plus the strict checker and immutable registration.

    Only the maintained verification checker is copied from the caller. Every
    calculation module and registered source artifact comes from the base.
    """
    spec = check_registration()
    base = spec["base_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("Registered base must be a full Git commit ID")
    try:
        git(REPO_ROOT, "cat-file", "-e", base + "^{commit}")
    except subprocess.CalledProcessError as error:
        raise ValueError(f"Registered base missing locally: {base}; no fetch attempted") from error
    with tempfile.TemporaryDirectory(prefix="stormscore-chips-verify-") as folder:
        root = Path(folder) / "checkout"
        git(REPO_ROOT, "clone", "--shared", "--no-checkout", "--no-tags", "--quiet",
            str(REPO_ROOT), str(root))
        git(root, "read-tree", base)
        git(root, "checkout-index", "--all", "--force")
        # Preserve the original registration history for check_registration's
        # git log/show checks, without substituting that revision's core files.
        git(root, "update-ref", "--no-deref", "HEAD", registration_commit())
        for relative in ("backend/storm/chips/__init__.py", "backend/storm/chips/protocol.py",
                         "docs/chips/preregistration.md"):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / relative, destination)
        for relative, expected in spec["source_sha256"].items():
            if sha256(root / relative) != expected:
                raise ValueError(f"Registered source mismatch in rebuilt base: {relative}")
        yield root


def snapshot_python(root: Path, code: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, "-c", code], cwd=root / "backend", env=env,
                          capture_output=True, text=True, timeout=60)
