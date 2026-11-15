"""Only historical runtime fingerprints need the original interpreter/libraries."""
import pytest

from storm.chips.historical import frozen_checkout, runtime_mismatches


@pytest.fixture
def registered_runtime():
    mismatches = runtime_mismatches()
    if mismatches:
        pytest.skip("Frozen-core fingerprint requires the registered runtime (" +
                    "; ".join(mismatches) + "). See "
                    "docs/chips/amendment-2026-11-15-historical-runtime.md; "
                    "this skip does not verify the historical fingerprint.")


@pytest.fixture
def registered_checkout(registered_runtime):
    with frozen_checkout() as root:
        yield root
