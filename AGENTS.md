# StormScore (DurHack 2026, SGX FX challenges)

Read this first in every session. Kamil keeps it short and updates it after each merge.

## What we're building
A storm defence for FX traders, shown as a live 3D sea. One flow: replay a real storm from SGX's data; the sea and sky turn; the alarm fires; two ships (one followed the alarm, one ignored it) show what the warning saved; a short storm report whose every number is checked by code.

Honest framing, from SGX's data: we found little advance warning in prices. So we (1) warn ahead for scheduled events from a calendar, (2) raise the alarm in the first minutes of unscheduled ones, (3) prepare the book with exposure and stress tests. Never claim to predict prices.

## Layout and ownership
No lane edits another lane's files. Shared files change only through Kamil.

| Path | Owner | Branch |
|---|---|---|
| backend/** except backend/storm/ai/** and backend/tests/ai/** | CC-L | lane/ccl-backend |
| backend/storm/ai/**, backend/tests/ai/** | CX | lane/cx-ai |
| tools/audio/**, web/src/audio/**, web/public/audio/** | CX | lane/cx-audio |
| web/** except web/src/audio/** and web/public/audio/** | CC-W | lane/ccw-web |
| contracts/**, CLAUDE.md, AGENTS.md, .gitignore, .env.example, caps.example.json, backend/requirements.txt, backend/storm/__init__.py, backend/storm/ai/__init__.py | Kamil | main |

Need a new dependency or a contract change? Don't edit shared files; say so in your PR description.

## Interfaces
- Replay bundle: contracts/replay_bundle.md is authoritative. Synthetic example: contracts/mock_storm.json.
- Real bundles: the backend writes web/public/bundles/<storm_id>.json and index.json locally. They are gitignored.
- Model calls: only through storm.ai.llm.complete(). Never call a provider SDK directly. Mock is the default; live calls need live=True or LLM_MODE=live and run only on Kamil's laptop.
- Budget guard: ledger ~/.stormscore/ledger.sqlite, caps ~/.stormscore/caps.json. Warn at 75%, refuse at 90%. Never edit the caps or the ledger.
- Scheduled events: contracts/calendar.csv (time_utc, event, region, source_url, verified).
- Sound: web/src/audio/engine.ts exposes createAudioEngine(). CC-W calls start() from the first user click, update() every animation frame and trigger() on events; CX implements it and never changes the interface without a PR. ElevenLabs assets are generated once by tools/audio/generate.py into web/public/audio/ (committed).

## Data
SGX zips live in data/raw/ (gitignored, never committed). 1-minute bars, 1 Jul to 31 Aug 2026, UTC. Pairs EURUSD, USDJPY, USDSGD; SPOT plus FORWARD 1W, 2W, 3W, 1M, 2M, 3M, 6M, 9M, 1Y. Spot columns: timestamp, settlement_date, then open/high/low/close as _bid/_ask/_mid. Forwards add *_fp (forward points) and *_mid_all_in. Sunday files start about 19:00 UTC; Fridays end about 21:00 UTC. Some USDSGD forward tenors miss a few days.

## Rules
- Never read, print or commit .env or any key.
- Never commit data/raw, data/processed or real bundles.
- No real personal data. The trader book is synthetic and labelled as such.
- Every number a user sees is computed by code from data. LLM text is verified against facts.
- Work only on your lane branch. Small commits, push often; Kamil merges at checkpoints.

## Commands
- Backend: cd backend && python -m pytest -q
- Web: cd web && npm run typecheck && npm run build
