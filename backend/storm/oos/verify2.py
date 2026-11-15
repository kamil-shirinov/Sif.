"""Registration-2 verification from its recorded core and original OOS implementation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .protocol import DOCS, REPO_ROOT, sha256
from .protocol2 import DATA2, REGISTRATION2, check_registration2
from .verify import git, restore_runner, safe_path


def verify_round2(data=DATA2):
    spec = check_registration2()
    saved = json.loads((DOCS / "results-2.json").read_text())
    prov = saved["provenance"]
    if prov["preregistration_sha256"] != sha256(REGISTRATION2) or saved["config"] != spec["config"]:
        raise ValueError("registration 2 result/registration mismatch")
    base, wrapper = spec["base_commit"], saved["execution"]["wrapper_commit_at_run"]
    if prov["base_commit"] != base or prov["code_fingerprint"] != spec["code_fingerprint"]:
        raise ValueError("registration 2 recorded core differs from registration")
    for name, digest in prov["amendment_sha256"].items():
        if Path(name).name != name or sha256(DOCS / name) != digest:
            raise ValueError("changed registration 2 amendment: " + name)
    if not (data / "manifest.json").is_file():
        raise ValueError("original round-two acquisition missing: " + str(data))
    for commit in (base, wrapper):
        git(REPO_ROOT, "cat-file", "-e", commit + "^{commit}")
    with tempfile.TemporaryDirectory(prefix="stormscore-oos2-verify-") as folder:
        root = Path(folder) / "checkout"
        git(REPO_ROOT, "clone", "--shared", "--no-checkout", "--no-tags", "--quiet", str(REPO_ROOT), str(root))
        git(root, "read-tree", base)
        git(root, "checkout-index", "--all", "--force")
        restore_runner(root, wrapper)
        git(root, "update-ref", "--no-deref", "HEAD", wrapper)
        for name, digest in prov["oos_source_sha256"].items():
            p = safe_path(name, "backend/storm/oos/")
            if sha256(root.joinpath(*p.parts)) != digest:
                raise ValueError("registration 2 runner source mismatch: " + name)
        for name in ("results-2.json", "results-2.md"):
            shutil.copyfile(DOCS / name, root / "docs/oos" / name)
        (root / "data/external").mkdir(parents=True, exist_ok=True)
        (root / "data/external/round2").symlink_to(data.resolve(), target_is_directory=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.pop("PYTHONPATH", None)
        print("Rebuilt registration 2 base", base, "runner", wrapper, flush=True)
        subprocess.run([sys.executable, "-m", "storm.oos.round2", "--verify-local"],
                       cwd=root / "backend", env=env, check=True)
