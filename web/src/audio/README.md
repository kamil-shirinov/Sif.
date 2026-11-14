# Market audio

`createAudioEngine()` keeps the existing `AudioFrame`, `AudioEvent`, and `AudioEngine`
interface. Call `start()` from a user click, `update(frame)` each animation frame,
and `trigger(event)` for discrete events. Mute is local to this engine; `dispose()`
releases players, synth, filters, gains, and pending announcements. Missing MP3s
are silent and do not prevent the rest of the audio from loading.

## Signal mapping

| Market signal | Sound | Source |
| --- | --- | --- |
| Risk, volatility ratio, storm state | Intensity `I = clamp(0.5*risk + 0.3*min(1,(volRatio-1)/8) + 0.2*(state===2), 0, 1)` | Browser calculation, smoothed to 95% of target in about 0.5 s |
| Intensity | Calm sea gain `1-I`, rough sea gain `I` | ElevenLabs sound effects: `sea_calm.mp3`, `sea_rough.mp3`, 20 s seamless loops |
| Intensity | Wind `smoothstep(0.2,0.8,I)` | ElevenLabs sound effects: `wind.mp3`, 20 s loop |
| Intensity | Rain `smoothstep(0.35,0.7,I)` | ElevenLabs sound effects: `rain.mp3`, 20 s loop |
| Intensity | Full storm `smoothstep(0.6,1,I)` | ElevenLabs sound effects: `storm.mp3`, 20 s loop |
| State 0 / 1 / 2 | Calm / tension / storm bed, linear crossfade over 2 s | ElevenLabs Music API: `music_calm.mp3`, `music_tension.mp3`, `music_storm.mp3`, 60 s each; requested C minor, 80 BPM, 20 bars |
| Intensity | Music low-pass opens linearly from 800 Hz to 12 kHz | Tone.js filter; also filters price melody |
| Absolute heel > 15 degrees | Timber creak, at most once every 4 s | ElevenLabs sound effects: `creak.mp3` |
| `jump` | Random thunder variant; linear amplitude `0.25 + 0.75*clamp(strength)` | ElevenLabs sound effects: `thunder_1.mp3` through `thunder_3.mp3` |
| `alarm` | Foghorn, then “Storm warning. Sharp move under way.” | ElevenLabs sound effects `foghorn.mp3`, then stock TTS `voice_alarm.mp3` |
| `cut` | Cargo crates splashing overboard | ElevenLabs sound effects: `splash.mp3` |
| `margin_call` | Ship sinking, then “Margin call.” | ElevenLabs sound effects `sinking.mp3`, then stock TTS `voice_margin_call.mp3` |
| `all_clear` | Bell, then “Storm passing.” | ElevenLabs sound effects `bell.mp3`, then stock TTS `voice_all_clear.mp3` |
| `watch` | Tension music follows state 1 in `update()` | Existing state mapping; no extra one-shot |
| `narrate` | Play an existing stock voice clip by ID (optional `.mp3` suffix) | `voice_alarm`, `voice_margin_call`, or `voice_all_clear`; unknown clips are silent |
| Any voice line | Music ducked 8 dB, ambience ducked 4 dB; 40 ms attack, 300 ms recovery | Browser gain buses; replacement speech keeps the duck active |
| New `minuteIndex` and price | Soft sine note on C minor pentatonic, C3–C5; higher price gives higher pitch; velocity follows absolute log return | Tone.js synthesis, no generated asset |
| Calm state | Melody only on minute indices divisible by four | Browser synthesis |
| Downward minute move of at least 0.3% that lowers the mapped note | Short falling pentatonic run, up to five notes 90 ms apart | Browser synthesis |

Price pitch is anchored to the first valid price in the replay. Log-price changes
of approximately +/-1% span the two octaves, with clipping outside that range.
Rewinding `minuteIndex` resets the anchor. Repeated render frames never retrigger
a minute. A new minute cancels unfinished run steps. Master and group gains leave
headroom for overlapping layers; the table describes relative layer gains.

## Generate once

The asset inventory, prompts, stock voice criteria, models, and editable credit
estimates live in `tools/audio/manifest.json`. There are **19 assets**: five ambience
loops, eight one-shots, three music beds, and three voice lines. No prompts name
real artists, songs, or people. The generator searches only premade British stock
voices, preferring calm narration, and never clones a voice or falls back to a
personal voice. TTS uses measured speed and high stability.

From the repository root, choose the Python environment:

```bash
if test -x ~/.venvs/stormscore/bin/python; then
  AUDIO_PYTHON=~/.venvs/stormscore/bin/python
else
  python3 -m venv work/audio-venv
  AUDIO_PYTHON="$PWD/work/audio-venv/bin/python"
  "$AUDIO_PYTHON" -m pip install -r backend/requirements.txt
fi
"$AUDIO_PYTHON" tools/audio/generate.py --dry-run
```

Dry-run prints every asset, its estimated credits, destination, and whether it
would generate or skip. It neither reads `.env` nor imports the SDK or makes
network calls. With the initial manifest rates, all assets total approximately
**8,502 credits**. These are planning assumptions, not a current price quote;
update them to match the account's rates before reviewing the spend. Use
`--dry-run --force` to estimate regenerating existing files.

**Kamil runs live generation only after review.** The live command is:

```bash
"$AUDIO_PYTHON" tools/audio/generate.py
```

Only that live path loads `ELEVENLABS_API_KEY` from the root `.env` at runtime,
without printing it. It writes `web/public/audio/<id>.mp3`, skips existing files
unless `--force`, and stops after at most 40 generation requests. SDK automatic
retries are disabled. Each response is written to a temporary `.part` file and
atomically replaces the destination after a complete nonempty download. A
failure stops the run and preserves the previous MP3.

Each attempted generation prints credits used from response usage headers. If
those are absent, it uses the before/after subscription usage delta, labelled
because concurrent account activity can affect it. If neither is available, it
prints `unknown` rather than claiming an estimate is actual usage. No exception
body, API key, or response headers are printed.

Audition the generated assets before committing them, especially the three
independently generated music beds: identical prompts for key, tempo, duration,
and downbeat guide the Music API but cannot guarantee musical alignment. The
browser starts all three beds on the same audio-clock downbeat. Regenerate a
specific unwanted asset by removing that MP3 and rerunning; `--force` regenerates
all existing assets and incurs fresh usage.

## Local checks and integration

```bash
cd tools/audio
npm install
npx tsc -p tsconfig.check.json
npm test
"$AUDIO_PYTHON" -m pytest -q test/test_generate.py
"$AUDIO_PYTHON" generate.py --dry-run
```

`tools/audio/package.json` owns the isolated Tone.js and TypeScript check
dependencies. `tsconfig.check.json` includes `../../web/src/audio` and resolves
Tone's real types from that isolated installation. The browser app must also
resolve `tone` (^15.1.22) through CC-W/Kamil's web dependencies when these branches
are integrated; this lane never edits `web/package.json`. The offline tests
exercise the real audio modules with a fake Tone surface and the generator with
fake SDK responses. They perform no generation and do not validate audible quality.
