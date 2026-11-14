"""All provider interactions are fakes. These tests never read .env or call an API."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("audio_generate", Path(__file__).parents[1] / "generate.py")
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


def test_dry_run_lists_all_assets_without_credentials(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(audio, "OUTPUT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["generate.py", "--dry-run"])
    import builtins
    original = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in {"dotenv", "elevenlabs"}
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    assert audio.main() == 0
    output = capsys.readouterr().out
    for asset in audio.load_manifest()["assets"]:
        assert asset["id"] in output
    assert "19 generations" in output
    assert "credits" in output
    assert not list(tmp_path.iterdir())


def test_existing_skip_force_and_40_generation_cap(monkeypatch, tmp_path):
    manifest = audio.load_manifest()
    monkeypatch.setattr(audio, "OUTPUT", tmp_path)
    (tmp_path / "sea_calm.mp3").write_bytes(b"existing")
    assert len(audio.print_plan(manifest, False)) == 18
    assert len(audio.print_plan(manifest, True)) == 19
    expanded = {**manifest, "assets": [dict(manifest["assets"][0], id=f"asset_{i}") for i in range(45)]}
    assert len(audio.print_plan(expanded, False)) == 40


class FakeClient:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        self.user = SimpleNamespace(subscription=SimpleNamespace(get=lambda **kw: SimpleNamespace(character_count=0)))
        endpoint = SimpleNamespace(convert=self.convert, compose=self.convert)
        self.text_to_sound_effects = SimpleNamespace(with_raw_response=endpoint)
        self.music = SimpleNamespace(with_raw_response=endpoint)
        self.text_to_speech = SimpleNamespace(with_raw_response=endpoint)

    @contextmanager
    def convert(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("private SDK body must never appear")
        yield SimpleNamespace(headers={"character-cost": "123"}, data=[b"fake audio"])


def test_live_paths_with_fake_sdk_only(monkeypatch, tmp_path, capsys):
    manifest = audio.load_manifest()
    client = FakeClient()
    monkeypatch.setattr(audio, "OUTPUT", tmp_path)
    monkeypatch.setattr(audio, "select_stock_voice", lambda *args: "stock-id")
    assert audio.generate(client, manifest["assets"], manifest) == 0
    assert len(client.calls) == 19
    assert len(list(tmp_path.glob("*.mp3"))) == 19
    assert all(call["request_options"]["max_retries"] == 0 for call in client.calls)
    assert all(call["loop"] is True for call in client.calls[:5])
    music = client.calls[13:16]
    assert all(call["music_length_ms"] == 60000 and call["force_instrumental"] for call in music)
    assert all("C minor" in call["prompt"] and "80 BPM" in call["prompt"] for call in music)
    assert "credits used = 123" in capsys.readouterr().out


def test_failed_generation_stops_and_preserves_old_asset(monkeypatch, tmp_path, capsys):
    manifest = audio.load_manifest()
    monkeypatch.setattr(audio, "OUTPUT", tmp_path)
    old = tmp_path / "sea_calm.mp3"
    old.write_bytes(b"old audio")
    client = FakeClient(fail=True)
    assert audio.generate(client, manifest["assets"], manifest) == 1
    assert len(client.calls) == 1
    assert old.read_bytes() == b"old audio"
    assert not list(tmp_path.glob("*.part"))
    assert "private SDK body" not in capsys.readouterr().err


def test_generate_enforces_cap_even_if_caller_passes_more(monkeypatch, tmp_path):
    manifest = audio.load_manifest()
    monkeypatch.setattr(audio, "OUTPUT", tmp_path)
    assets = [dict(manifest["assets"][0], id=f"asset_{i}") for i in range(45)]
    client = FakeClient()
    assert audio.generate(client, assets, manifest) == 0
    assert len(client.calls) == 40


def test_voice_selection_rejects_clones_and_prefers_calm_british():
    def voice(voice_id, category, accent, description):
        return SimpleNamespace(voice_id=voice_id, category=category, labels={"accent": accent}, description=description)
    response = SimpleNamespace(voices=[
        voice("clone", "cloned", "british", "calm narration measured clear"),
        voice("american", "premade", "american", "calm narration measured clear"),
        voice("stock-bright", "premade", "british", "bright"),
        voice("stock-calm", "premade", "british", "calm narration measured clear"),
    ], has_more=False, next_page_token=None)
    client = SimpleNamespace(voices=SimpleNamespace(search=lambda **kw: response))
    assert audio.select_stock_voice(client, audio.load_manifest()) == "stock-calm"


def test_real_sdk_request_shapes_over_mock_transport(monkeypatch, tmp_path):
    """The actual SDK serializes requests into a local mock, never the network."""
    import httpx
    from elevenlabs.client import ElevenLabs
    import json

    requests = []

    def respond(request):
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, content=b"offline fake bytes", headers={"character-cost": "7"})

    manifest = audio.load_manifest()
    monkeypatch.setattr(audio, "OUTPUT", tmp_path)
    monkeypatch.setattr(audio, "credit_count", lambda _: None)
    monkeypatch.setattr(audio, "select_stock_voice", lambda *args: "stock-id")
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = ElevenLabs(api_key="offline-fake-key", httpx_client=http)
        assert audio.generate(client, manifest["assets"], manifest) == 0
    assert len(requests) == 19
    assert all(path == "/v1/sound-generation" for path, _ in requests[:13])
    assert all(body["loop"] is True for _, body in requests[:5])
    assert all(body["music_length_ms"] == 60000 for _, body in requests[13:16])
    assert [body["text"] for _, body in requests[16:]] == [asset["text"] for asset in manifest["assets"][16:]]
