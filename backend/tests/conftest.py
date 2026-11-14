import pytest

from storm.paths import RAW_DIR

USDJPY_SPOT_ZIP = RAW_DIR / "USDJPY_USD_SPOT_SPOT_1000000_20260701-20260831.zip"

needs_raw = pytest.mark.skipif(not USDJPY_SPOT_ZIP.exists(), reason="SGX data not in data/raw")
