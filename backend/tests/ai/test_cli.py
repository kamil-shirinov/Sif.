import json

from storm.ai import bakeoff, report, smoke


def test_report_cli(bundle, tmp_path, capsys):
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle))
    assert report.main(["--bundle", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["verified"] and result["inspector"]["verdict"] == "ok"


def test_offline_smoke(capsys):
    assert smoke.main([]) == 0
    assert "mock: ok" in capsys.readouterr().out


def test_offline_bakeoff_skips_index(bundle, tmp_path, capsys):
    (tmp_path / "index.json").write_text('{"storms":[]}')
    (tmp_path / "mock_storm.json").write_text(json.dumps(bundle))
    assert bakeoff.main(["--models", "muse-spark-1.1,muse-spark-1.3", "--bundles", str(tmp_path)]) == 0
    results = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(results) == 2
    for result in results:
        assert result["reports"] == 1 and result["errors"] == 0
        assert result["first_try_verification_rate"] == 1
        assert result["inspector_flags"] == 0 and result["cost_per_report_usd"] == 0


def test_bakeoff_requires_bundles(tmp_path):
    assert bakeoff.main(["--models", "muse-spark-1.1", "--bundles", str(tmp_path)]) == 1
