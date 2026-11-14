# Generated audio — 14 November 2026

Status: all 19 MP3s generated and verified in `web/public/audio/`.

- Branch: `assets/audio`, based on `main` at `7938f60`.
- Interpreter: `~/.venvs/stormscore/bin/python`.
- Credentials loaded privately via `STORM_ENV_FILE`; no credentials recorded.
- Initial dry run: 19 generations, 8,502 estimated credits.
- Successful run: 19 generation calls, no failures or retries; 40-call cap unchanged.
- Mutagen parsed every MP3; all have a 44,100 Hz sample rate.
- Five ambience loops are 20.036 s against 20 s requested. Three music loops
  are 60.082 s against 60 s requested. Maximum loop duration difference:
  0.082 s. This verifies duration, not perceived seam quality.
- Final directory check: 19 MP3s plus `.gitkeep`; no partial files.
- Final dry run: every asset skipped as existing, zero planned generations.

## Durations and credits

Credit values in the table come only from individual generation response
headers. Music responses did not include individual credit counts.

| ID | Type | Requested | Measured duration | Response credits |
|---|---|---|---|---|
| sea_calm | sfx | 20 s | 20.036 s | 220 |
| sea_rough | sfx | 20 s | 20.036 s | 220 |
| wind | sfx | 20 s | 20.036 s | 220 |
| rain | sfx | 20 s | 20.036 s | 220 |
| storm | sfx | 20 s | 20.036 s | 220 |
| thunder_1 | sfx | 5 s | 5.042 s | 55 |
| thunder_2 | sfx | 5 s | 5.042 s | 55 |
| thunder_3 | sfx | 6 s | 6.034 s | 66 |
| foghorn | sfx | 4 s | 4.049 s | 44 |
| splash | sfx | 3 s | 3.030 s | 33 |
| creak | sfx | 2 s | 2.038 s | 22 |
| sinking | sfx | 8 s | 8.046 s | 88 |
| bell | sfx | 3 s | 3.030 s | 33 |
| music_calm | music | 60 s | 60.082 s | not reported |
| music_tension | music | 60 s | 60.082 s | not reported |
| music_storm | music | 60 s | 60.082 s | not reported |
| voice_alarm | tts | speech | 2.743 s | 16 |
| voice_margin_call | tts | speech | 1.280 s | 5 |
| voice_all_clear | tts | speech | 1.489 s | 6 |

## Billing evidence

- Confirmed individual response charges: **1523 credits**
  (1,496 sound effects + 27 speech).
- Music account-usage deltas observed immediately around each request:
  0, 0, 2761 credits. These may include delayed or concurrent account activity
  and cannot reliably be attributed to the corresponding music track.
- The generator reported an aggregate of **4284 credits** by adding
  response charges and those account deltas. This is an observed mixed-source
  sum, **not an independently verified final billing total**; delayed charges
  may overlap values already counted from response headers.
- Read-only usage queries for the run window and aligned hour returned no
  usage data. Matching speech history confirmed the three speech charges
  (16, 5 and 6 credits), but supplied no sound-effect or music records.
- Final actual total: not independently verifiable from the available API
  responses. No extra billable generations were made for accounting checks.

## Earlier attempts

The earlier restricted key caused two failed `sea_calm` attempts in each of
two authorised runs. Each run stopped at its two-failure limit without
creating MP3s. After Kamil replaced the key and authorised this run, all assets
succeeded on the first attempt.
