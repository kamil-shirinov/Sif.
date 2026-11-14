"""Repository paths shared by the backend modules."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
BUNDLES_DIR = REPO_ROOT / "web" / "public" / "bundles"
CALENDAR_CSV = REPO_ROOT / "contracts" / "calendar.csv"
MOCK_BUNDLE = REPO_ROOT / "contracts" / "mock_storm.json"
