import copy
import json

from storm.paths import MOCK_BUNDLE
from storm.validate import main, validate_bundle, validate_index


def _mock():
    return json.loads(MOCK_BUNDLE.read_text())


def test_mock_bundle_is_valid():
    assert validate_bundle(_mock()) == []
    assert main([str(MOCK_BUNDLE)]) == 0


def test_short_series_is_rejected():
    b = _mock()
    b["series"]["risk"] = b["series"]["risk"][:-1]
    assert any("series.risk: length" in e for e in validate_bundle(b))


def test_missing_and_extra_keys_and_bad_types():
    b = _mock()
    del b["ships"]["prepared"]["cut_i"]
    b["surprise"] = 1
    b["series"]["state"][0] = 3
    b["book_is_synthetic"] = 1
    errors = validate_bundle(b)
    assert any("ships.prepared.cut_i: missing" in e for e in errors)
    assert any("bundle.surprise" in e for e in errors)
    assert any("series.state" in e for e in errors)
    assert any("book_is_synthetic" in e for e in errors)


def test_event_fields_by_type():
    b = _mock()
    b["events"].append({"i": 5, "type": "watch", "text": "Watch"})  # no at_i
    b["events"].append({"i": 10_000, "type": "all_clear", "text": "x"})
    errors = validate_bundle(copy.deepcopy(b))
    assert any("at_i: missing" in e for e in errors)
    assert any("outside" in e for e in errors)


def test_index_shape():
    ix = {"schema_version": 1, "storms": [{"storm_id": "a", "title": "t", "symbol": "USDJPY",
          "asset_class": "fx", "kind": "unscheduled", "move_bp": -1.0, "file": "a.json"}], "metrics": None}
    assert validate_index(ix) == []
    ix["storms"][0].pop("file")
    assert validate_index(ix) != []
