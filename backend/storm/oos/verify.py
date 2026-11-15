"""Rebuild the registered core and original runner in a disposable local checkout.

No worktree, index, ref or tracked file in the caller is changed. The child runs
the *recorded* runner, including its original provenance checks, rather than
substituting today's implementation for the historical one.
"""
from __future__ import annotations

from contextlib import contextmanager
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

from .protocol import (DATA, DOCS, REPO_ROOT, check_registration, sha256)


def git(root: Path, *args: str) -> bytes:
    # Only local object reads and operations in the disposable clone. No fetch.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.check_output(["git", "-C", str(root), *args], env=env,
                                   stderr=subprocess.PIPE)


def safe_path(value: str, prefix: str) -> PurePosixPath:
    path = PurePosixPath(value)
    parent = PurePosixPath(prefix)
    if path.is_absolute() or ".." in path.parts or (path != parent and parent not in path.parents):
        raise ValueError(f"unexpected historical artifact path: {value}")
    return path


def recorded_artifacts(saved: dict) -> tuple[dict, str, str]:
    spec = check_registration()
    provenance = saved["provenance"]
    if provenance["preregistration_sha256"] != sha256(DOCS / "preregistration.md"):
        raise ValueError("results use a different preregistration")
    if saved["config"] != spec["config"] or provenance["frozen_config_sha256"] != spec["config_sha256"]:
        raise ValueError("recorded config differs from registration")
    if provenance["code_fingerprint"] != spec["code_fingerprint"]:
        raise ValueError("recorded core fingerprint differs from registration")
    # Amendments added after the run are not inputs to that run. Validate every
    # recorded amendment and note without adding new files to old provenance.
    for name, digest in provenance["amendment_sha256"].items():
        if PurePosixPath(name).name != name or sha256(DOCS / name) != digest:
            raise ValueError(f"changed recorded amendment: {name}")
    if sha256(DOCS / "acquisition_notes.md") != provenance["acquisition_notes_sha256"]:
        raise ValueError("changed recorded acquisition notes")
    base, wrapper = spec["base_commit"], saved["execution"]["wrapper_commit_at_run"]
    if any(not re.fullmatch(r"[0-9a-f]{40}", commit) for commit in (base, wrapper)):
        raise ValueError("recorded revisions must be full Git commit IDs")
    for commit in (base, wrapper):
        try:
            git(REPO_ROOT, "cat-file", "-e", commit + "^{commit}")
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"required historical commit missing locally: {commit}; no network fetch attempted") from exc
    return spec, base, wrapper


def restore_runner(root: Path, wrapper: str) -> None:
    archive = git(root, "archive", wrapper, "--", "backend/storm/oos", "docs/oos")
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            if member.isdir() and member.name.rstrip("/") in ("backend", "backend/storm", "docs"):
                continue
            prefix = "backend/storm/oos" if member.name.startswith("backend/") else "docs/oos"
            relative = safe_path(member.name, prefix)
            target = root.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as stream:
                    target.write_bytes(stream.read())
            else:
                raise ValueError(f"unsupported historical archive entry: {member.name}")


@contextmanager
def frozen_checkout(data: Path | None = None):
    """Materialise base_commit plus the exact recorded runner; optionally link data."""
    saved = json.loads((DOCS / "results.json").read_text())
    _, base, wrapper = recorded_artifacts(saved)
    if data is not None and not (data / "manifest.json").is_file():
        raise ValueError(f"original acquisition data missing: {data / 'manifest.json'}")
    with tempfile.TemporaryDirectory(prefix="stormscore-oos-verify-") as folder:
        root = Path(folder) / "checkout"
        # --shared reads the local object database; --no-checkout avoids hooks
        # and the caller's current tree. No remote contact or shared ref writes.
        git(REPO_ROOT, "clone", "--shared", "--no-checkout", "--no-tags", "--quiet",
            str(REPO_ROOT), str(root))
        git(root, "read-tree", base)
        git(root, "checkout-index", "--all", "--force")
        restore_runner(root, wrapper)
        # Old protocol.py uses git log to find the registration's first commit.
        # Give this temporary repo the original runner's history, while its
        # core files/index remain explicitly materialised from base_commit.
        git(root, "update-ref", "--no-deref", "HEAD", wrapper)
        for name, digest in saved["provenance"]["oos_source_sha256"].items():
            path = safe_path(name, "backend/storm/oos/")
            if sha256(root.joinpath(*path.parts)) != digest:
                raise ValueError(f"historical runner source hash mismatch: {name}")
        for name in ("results.json", "results.md"):
            shutil.copyfile(DOCS / name, root / "docs" / "oos" / name)
        if data is not None:
            (root / "data").mkdir(exist_ok=True)
            (root / "data" / "external").symlink_to(data.resolve(), target_is_directory=True)
        yield root


def verify_saved(data: Path = DATA) -> None:
    with frozen_checkout(data) as root:
        spec = json.loads((DOCS / "results.json").read_text())
        print("Rebuilt registered base " + check_registration()["base_commit"] +
              " with recorded runner " + spec["execution"]["wrapper_commit_at_run"], flush=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.pop("PYTHONPATH", None)
        subprocess.run([sys.executable, "-m", "storm.oos.run", "--verify"],
                       cwd=root / "backend", env=env, check=True)
