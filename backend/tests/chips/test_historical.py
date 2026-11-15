"""Historical core verification survives runtime and caller-source changes."""
import hashlib
import json

import pytest

from storm.chips.historical import (frozen_checkout, git, registered_runtime,
                                    runtime_mismatches, snapshot_python)
from storm.chips.protocol import DOCS, REPO_ROOT, registration, sha256


def test_rebuild_uses_registered_sources_instead_of_callers_core(monkeypatch):
    import storm.chips.historical as historical
    import storm.chips.protocol as protocol

    def must_not_fingerprint_current_main():
        raise AssertionError("Historical verification inspected the caller's current core")

    monkeypatch.setattr(protocol, "code_fingerprint", must_not_fingerprint_current_main)
    base = registration()["base_commit"]
    with frozen_checkout() as caller:
        # Simulate a later main commit in a disposable caller, never the real
        # checkout. Rebuilding HEAD or copying its dirty sources would be wrong.
        relative = "backend/storm/detector.py"
        source = caller / relative
        source.write_bytes(source.read_bytes() + b"\n# Legitimate later backend change.\n")
        git(caller, "-c", "user.name=Chips test", "-c", "user.email=chips-test@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "--quiet", "--only", "-m", "Later backend change",
            "--", relative)
        monkeypatch.setattr(historical, "REPO_ROOT", caller)
        with frozen_checkout() as root:
            for name in registration()["source_sha256"]:
                assert (root / name).read_bytes() == git(REPO_ROOT, "show", f"{base}:{name}")
            assert (root / relative).read_bytes() != source.read_bytes()
    assert not root.exists()
    assert not caller.exists()


def test_registered_core_fingerprint_is_still_strict(registered_checkout):
    result = snapshot_python(registered_checkout,
                             "from storm.chips.protocol import check_frozen; check_frozen()")
    assert result.returncode == 0, result.stderr


def test_real_constant_change_under_registered_runtime_is_rejected(registered_checkout):
    result = snapshot_python(registered_checkout,
                             "import storm.labels; storm.labels.MIN_MOVE_BP = 31.0; "
                             "from storm.chips.protocol import check_frozen; check_frozen()")
    assert result.returncode != 0
    assert "Frozen core fingerprint mismatch" in result.stderr


@pytest.mark.parametrize("relative, message", [
    ("backend/storm/detector.py", "Frozen core fingerprint mismatch"),
    ("backend/storm/ai/report.py", "Frozen source changed: backend/storm/ai/report.py"),
])
def test_real_source_change_under_registered_runtime_is_rejected(registered_checkout, relative, message):
    source = registered_checkout / relative
    source.write_bytes(source.read_bytes() + b"\n# Deliberate drift in a disposable checkout.\n")
    result = snapshot_python(registered_checkout,
                             "from storm.chips.protocol import check_frozen; check_frozen()")
    assert result.returncode != 0
    assert message in result.stderr


def test_runtime_amendment_matches_original_library_provenance():
    saved = json.loads((DOCS / "results.json").read_text())
    expected = registered_runtime()
    assert expected["implementation"] == "CPython"
    assert expected["python"] == "3.10.0"
    for library in ("numpy", "pandas", "pyarrow"):
        assert expected[library] == saved["acquisition"]["versions"][library]


def test_runtime_mismatch_lists_different_interpreter_and_library(monkeypatch):
    import storm.chips.historical as historical

    expected = registered_runtime()
    monkeypatch.setattr(historical.platform, "python_implementation", lambda: expected["implementation"])
    monkeypatch.setattr(historical.platform, "python_version", lambda: "3.12.13")
    monkeypatch.setattr(historical.importlib.metadata, "version",
                        lambda name: "different" if name == "numpy" else expected[name])
    assert runtime_mismatches() == ["python: registered 3.10.0, running 3.12.13",
                                    f"numpy: registered {expected['numpy']}, running different"]


def test_results_and_registration_remain_byte_for_byte_unchanged():
    for name in ("preregistration.md", "results.json", "results.md"):
        original = git(REPO_ROOT, "show", f"eeab16c:docs/chips/{name}")
        assert sha256(DOCS / name) == hashlib.sha256(original).hexdigest()
