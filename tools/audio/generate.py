#!/usr/bin/env python3
"""Generate reviewed audio once. --dry-run never loads credentials or the SDK."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("manifest.json")
OUTPUT = ROOT / "web/public/audio"
MAX_GENERATIONS = 40
REQUEST_OPTIONS = {"max_retries": 0, "timeout_in_seconds": 180}


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    manifest = json.loads(path.read_text())
    seen: set[str] = set()
    for asset in manifest["assets"]:
        asset_id = asset["id"]
        if not re.fullmatch(r"[a-z0-9_]+", asset_id) or asset_id in seen:
            raise ValueError("Asset IDs must be unique safe filenames")
        seen.add(asset_id)
        if asset["kind"] not in {"sfx", "music", "tts"}:
            raise ValueError("Unknown asset kind")
    return manifest


def estimate_credits(asset: dict[str, Any], manifest: dict[str, Any]) -> int:
    rates = manifest["credit_estimates"]
    if asset["kind"] == "tts":
        return math.ceil(len(asset["text"]) * rates["tts_per_character"])
    if asset["kind"] == "music":
        return math.ceil(asset["duration_seconds"] / 60 * rates["music_per_minute"])
    return math.ceil(asset["duration_seconds"] * rates["sfx_per_second"])


def print_plan(manifest: dict[str, Any], force: bool) -> list[dict[str, Any]]:
    pending = []
    total = 0
    for asset in manifest["assets"]:
        cost = estimate_credits(asset, manifest)
        exists = (OUTPUT / f'{asset["id"]}.mp3').exists()
        action = "skip existing" if exists and not force else "generate"
        if action == "generate":
            if len(pending) < MAX_GENERATIONS:
                pending.append(asset)
                total += cost
            else:
                action = "defer: 40-call limit"
        duration = f'{asset["duration_seconds"]}s' if "duration_seconds" in asset else "speech"
        print(f'{asset["id"]:20} {asset["kind"]:5} {duration:6} '
              f'~{cost:5} credits | {action} -> web/public/audio/{asset["id"]}.mp3')
    print(f"Planned: {len(pending)} generations; estimated {total} credits; hard limit {MAX_GENERATIONS}.")
    print(manifest["credit_estimates"]["note"])
    return pending


def select_stock_voice(client: Any, manifest: dict[str, Any]) -> str:
    """Select only a premade British voice; never use cloning or personal voices."""
    token = None
    candidates = []
    while True:
        result = client.voices.search(
            voice_type="default", category="premade", accent=manifest["voice"]["accent"],
            page_size=100, next_page_token=token, request_options=REQUEST_OPTIONS,
        )
        for voice in result.voices:
            labels = voice.labels or {}
            if voice.category == "premade" and "british" in labels.get("accent", "").lower():
                description = " ".join([voice.description or "", *labels.values()]).lower()
                score = sum(word in description for word in ("calm", "narration", "measured", "clear"))
                candidates.append((score, voice.voice_id))
        token = result.next_page_token
        if not result.has_more or not token:
            break
    if not candidates:
        raise RuntimeError("No premade British stock voice available; no clone fallback")
    return sorted(candidates, key=lambda item: (-item[0], item[1]))[0][1]


def credit_count(client: Any) -> int | None:
    try:
        return int(client.user.subscription.get(request_options=REQUEST_OPTIONS).character_count)
    except Exception:
        return None


def response_credits(headers: Any) -> float | None:
    # Never print headers: they may include sensitive service metadata.
    for key in ("x-credits-used", "credits-used", "character-cost", "x-character-count"):
        value = headers.get(key)
        if value is not None:
            try:
                amount = float(value)
                if math.isfinite(amount) and amount >= 0:
                    return amount
            except (TypeError, ValueError):
                pass
    return None


def request_audio(client: Any, asset: dict[str, Any], manifest: dict[str, Any], voice_id: str | None) -> Any:
    common = {"output_format": "mp3_44100_128", "request_options": REQUEST_OPTIONS}
    kind = asset["kind"]
    if kind == "sfx":
        return client.text_to_sound_effects.with_raw_response.convert(
            text=asset["prompt"], loop=asset["loop"], duration_seconds=asset["duration_seconds"],
            model_id=manifest["models"]["sfx"], **common,
        )
    if kind == "music":
        return client.music.with_raw_response.compose(
            prompt=manifest["music"]["shared_prompt"] + " " + asset["prompt"],
            music_length_ms=asset["duration_seconds"] * 1000, force_instrumental=True,
            model_id=manifest["models"]["music"], **common,
        )
    from elevenlabs import VoiceSettings
    return client.text_to_speech.with_raw_response.convert(
        voice_id=voice_id, text=asset["text"], model_id=manifest["models"]["tts"],
        voice_settings=VoiceSettings(stability=manifest["voice"]["stability"],
                                     similarity_boost=0.75, speed=manifest["voice"]["speed"]),
        **common,
    )


def generate(client: Any, pending: list[dict[str, Any]], manifest: dict[str, Any]) -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    voice_id = None
    for number, asset in enumerate(pending[:MAX_GENERATIONS], 1):
        if asset["kind"] == "tts" and voice_id is None:
            voice_id = select_stock_voice(client, manifest)
        destination = OUTPUT / f'{asset["id"]}.mp3'
        partial = destination.with_suffix(".mp3.part")
        before = credit_count(client)
        used = None
        try:
            # SDK automatic retries are disabled so a retry cannot incur an uncounted generation.
            with request_audio(client, asset, manifest, voice_id) as response:
                used = response_credits(response.headers)
                with partial.open("wb") as output:
                    for chunk in response.data:
                        output.write(chunk)
            if not partial.stat().st_size:
                raise RuntimeError("Empty audio response")
            partial.replace(destination)
        except Exception as error:
            partial.unlink(missing_ok=True)
            # SDK exception bodies can contain request details; never print them.
            print(f'{asset["id"]}: failed ({type(error).__name__}); stopping without retry.', file=sys.stderr)
            return 1
        finally:
            if used is None:
                after = credit_count(client)
                if before is not None and after is not None and after >= before:
                    used = after - before
                    source = "account usage delta; includes concurrent account activity"
                else:
                    source = "usage unavailable from API"
            else:
                source = "API response"
            amount = f"{used:g}" if used is not None else "unknown"
            print(f'{number}/{MAX_GENERATIONS} {asset["id"]}: credits used = {amount} ({source})')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print plan and estimates; no credentials or network")
    parser.add_argument("--force", action="store_true", help="Regenerate existing files (billable without --dry-run)")
    args = parser.parse_args()
    manifest = load_manifest()
    pending = print_plan(manifest, args.force)
    if args.dry_run or not pending:
        return 0

    # Only Kamil runs this live path after review. Never load .env in dry-run.
    from dotenv import load_dotenv
    from elevenlabs.client import ElevenLabs
    load_dotenv(ROOT / ".env", override=False)
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        print("ELEVENLABS_API_KEY is required for live generation.", file=sys.stderr)
        return 1
    try:
        return generate(ElevenLabs(api_key=key), pending, manifest)
    except Exception as error:
        print(f"Generation stopped ({type(error).__name__}); no automatic retry.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
