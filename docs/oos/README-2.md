# Reproduce registration 2

The immutable [second registration](preregistration-2.md) was pushed alone at `5f39e45`
before acquisition. It freezes main `3625e41`, the unchanged tuned config and the current
calculation fingerprints. The three acquisition amendments document sandbox permissions,
the feed's HTTP-to-HTTPS redirect, and bounded completion of partial daily artifacts.
They were pushed before their corresponding continuation and before any detector run.
The [warm-up clarification](amendment-2-2026-11-15-warmup.md) preserves valid December
history independently of January coverage, without relaxing either eligibility threshold.
The original registration 1 and published result files remain unchanged.

Use CPython 3.10.0, NumPy 2.2.6, pandas 2.3.3 and PyArrow 24.0.0 for exact verification.
The original runtime amendment explains why newer Python/library versions can change
runtime-aware fingerprints even when Git source is identical. Pytest's runtime-specific
historical checks skip explicitly under other versions; verification remains strict.

Local layout (never committed):

```text
data/external/round1/   original registration-1 artifact root, or a directory link to it
data/external/round2/   independent registration-2 artifact root
```

The registration-1 directory must not contain round-two artifacts: its original inventory
is exact. The round-two root retains every failed setup/transport pass, all response
bodies and logs, the conservative exhausted-URL list, continuation plan, raw CSVs,
per-pair/month ingest-compatible parquet files and the final chronological manifest.
The local Git exclude rule ignores `data/external/`; shared ignore/dependency files are
unchanged. No SGX prices or live model APIs are used.

```sh
cd backend
python -m pytest -q
python -m storm.oos.run --verify
```

The combined verifier reconstructs each registration's own base and original recorded
runner from local Git objects. It checks both exact result JSONs and deterministic
Markdown, including weekly policy fills, frozen sources, config/runtime and every data
hash. It never reacquires data. Alternative locations:

```sh
python -m storm.oos.run --verify --data-dir /original/round1/artifacts --round-two-data-dir /original/round2/artifacts
```

The primary round-two command is `python -m storm.oos.round2`. Its committed one-shot
marker prevents another primary run; use verification for recomputation. The original
runner revision and source hashes are recorded in results-2.json. No thresholds are
selected or tuned. Synthetic unit tests compare weekly execution with the unchanged
core engine, exercise carry-in alarm cuts/restores, check chronological prefix selection
and prove that monthly/weekly outputs share a single detector pass per pair.

Round-two June 2025 EURUSD/USDJPY/GBPUSD overlaps the first study, as registered. It is
included transparently rather than described as new unseen evidence. All weekly books
are synthetic, independently reset long-USD $20m positions on $1m equity per pair.
The carry-in convention and partial-week coverage rules are explicit in the registration.
All planned instruments have a USD leg; no unsupported non-USD cross is silently valued.
