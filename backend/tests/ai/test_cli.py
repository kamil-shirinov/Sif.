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


def test_smoke_uses_low_reasoning_and_accepts_any_nonempty_text(monkeypatch, capsys):
    from storm.ai import llm

    requests = []
    monkeypatch.setenv("FIREWORKS_MODEL_CHECKER", "kimi-k3p1-pro")
    monkeypatch.delenv("MODAL_BASE_URL", raising=False)
    monkeypatch.setattr(llm, "list_models", lambda *a, **k: ["test-model"])

    def complete(messages, **kwargs):
        requests.append((messages, kwargs))
        # A non-empty answer is sufficient even when tool metadata exists.
        return {"text": "Ready", "tool_calls": [{"id": "ignored"}], "model": kwargs["model"], "cost_usd": 0}

    monkeypatch.setattr(llm, "complete", complete)
    assert smoke.main(["--live"]) == 0
    assert [kwargs["max_tokens"] for _, kwargs in requests] == [1024, 1024]
    assert [kwargs["reasoning_effort"] for _, kwargs in requests] == ["minimal", "low"]
    assert all("one word" in messages[0]["content"] for messages, _ in requests)
    assert "meta: ok" in capsys.readouterr().out


def test_smoke_prints_reasoning_exhaustion_diagnostics_from_mock(monkeypatch, capsys):
    from storm.ai import llm

    monkeypatch.setattr(llm, "_mock", lambda *a: ("", [], "length"))
    assert smoke.main([]) == 1
    output = capsys.readouterr().out
    assert "max_tokens was used up by reasoning" in output
    diagnostic = json.loads(output.splitlines()[-1])
    assert diagnostic["finish_reason"] == "length"
    assert diagnostic["usage"]["completion_tokens"] == 1024
    assert diagnostic["raw_message"]
