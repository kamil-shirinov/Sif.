"""Historical verification survives later core edits without weakening provenance."""
import hashlib
import json
import subprocess

import pytest

from storm.oos.protocol import DOCS, REGISTRATION, REPO_ROOT, registration, sha256
from storm.oos.verify import frozen_checkout, recorded_artifacts, safe_path


def test_rebuild_ignores_callers_current_calculation_modules(monkeypatch):
    import storm.oos.protocol as protocol

    def must_not_use_current_core():
        raise AssertionError("historical verification inspected current core fingerprint")

    monkeypatch.setattr(protocol, "code_fingerprint", must_not_use_current_core)
    base = registration()["base_commit"]
    with frozen_checkout() as root:
        for name in ("exposure.py", "export.py", "equity.py"):
            path = f"backend/storm/{name}"
            expected = subprocess.check_output(["git", "show", f"{base}:{path}"], cwd=REPO_ROOT)
            assert (root / path).read_bytes() == expected
        assert sha256(root / "docs" / "metrics.md") == registration()["metrics_document_sha256"]
        saved = json.loads((DOCS / "results.json").read_text())
        for path, digest in saved["provenance"]["oos_source_sha256"].items():
            assert sha256(root / path) == digest
        # Only the amendments used for the original run enter its provenance.
        assert {p.name for p in (root / "docs" / "oos").glob("amendment-*.md")} == set(saved["provenance"]["amendment_sha256"])
        assert not (root / "backend" / "storm" / "oos" / "verify.py").exists()
    assert not root.exists()


def test_missing_original_data_fails_before_reconstruction(tmp_path):
    with pytest.raises(ValueError, match="original acquisition data missing"):
        with frozen_checkout(tmp_path):
            pytest.fail("missing data was accepted")


def test_recorded_config_cannot_be_changed():
    saved = json.loads((DOCS / "results.json").read_text())
    saved["config"]["storm_on"] += 0.01
    with pytest.raises(ValueError, match="recorded config differs"):
        recorded_artifacts(saved)


@pytest.mark.parametrize("path", ["/tmp/elsewhere", "backend/storm/oos/../../exposure.py",
                                  "backend/storm/oos-other/run.py"])
def test_snapshot_paths_cannot_escape_registered_runner(path):
    with pytest.raises(ValueError, match="unexpected historical artifact path"):
        safe_path(path, "backend/storm/oos/")


def test_recorded_results_and_registration_have_not_been_rewritten():
    original = subprocess.check_output(["git", "show", "9b34226:docs/oos/results.json"], cwd=REPO_ROOT)
    assert sha256(DOCS / "results.json") == hashlib.sha256(original).hexdigest()
    original = subprocess.check_output(["git", "show", "a849bfe:docs/oos/preregistration.md"], cwd=REPO_ROOT)
    assert sha256(REGISTRATION) == hashlib.sha256(original).hexdigest()
