"""Only runtime-sensitive historical fingerprint tests require the original runtime."""
import json
import platform

import numpy
import pandas
import pyarrow
import pytest

from storm.oos.protocol import DOCS


@pytest.fixture
def registered_runtime():
    recorded = json.loads((DOCS / "results.json").read_text())["execution"]
    expected = {"implementation": "CPython", **{name: recorded[name] for name in
                                               ("python", "numpy", "pandas", "pyarrow")}}
    running = {"implementation": platform.python_implementation(), "python": platform.python_version(),
               "numpy": numpy.__version__, "pandas": pandas.__version__, "pyarrow": pyarrow.__version__}
    mismatches = [f"{name}: registered {value}, running {running[name]}"
                  for name, value in expected.items() if running[name] != value]
    if mismatches:
        pytest.skip("Frozen-core fingerprint requires the registered runtime (" +
                    "; ".join(mismatches) + "). See docs/oos/amendment-2026-11-15-runtime.md; "
                    "this skip does not verify the historical fingerprint.")
