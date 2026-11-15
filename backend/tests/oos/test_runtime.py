"""A version mismatch skips before fingerprinting, rather than hiding code drift."""
import platform

import numpy
import pandas
import pyarrow
import pytest


@pytest.mark.parametrize("component", ["implementation", "python", "numpy", "pandas", "pyarrow"])
def test_each_runtime_mismatch_skips_with_registered_and_running_versions(component, monkeypatch, request):
    if component == "implementation":
        monkeypatch.setattr(platform, "python_implementation", lambda: "different-interpreter")
        running = "different-interpreter"
    elif component == "python":
        monkeypatch.setattr(platform, "python_version", lambda: "0.0.0")
        running = "0.0.0"
    else:
        monkeypatch.setattr({"numpy": numpy, "pandas": pandas, "pyarrow": pyarrow}[component],
                            "__version__", "0.0.0")
        running = "0.0.0"
    with pytest.raises(pytest.skip.Exception) as skipped:
        request.getfixturevalue("registered_runtime")
    reason = str(skipped.value)
    assert f"{component}: registered " in reason
    assert f"running {running}" in reason
    assert "amendment-2026-11-15-runtime.md" in reason
    assert "does not verify the historical fingerprint" in reason
