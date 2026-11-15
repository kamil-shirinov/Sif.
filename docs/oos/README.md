# Reproducing the frozen holdout

The immutable protocol is [preregistration.md](preregistration.md), pushed by itself
before data acquisition. The two dated amendments record failed HTTPS acquisition and
the switch to the official HTTP endpoint, both before the first scored detector run.
Only transport changed in those amendments. [Acquisition notes](acquisition_notes.md)
record a pre-score decoder correction needed to enforce the registered zero-volume
exclusion; the saved raw feed bodies were re-decoded without another download.
Read the protocol for precise endpoints and limitations.

[Validation](validation.md) records the whole-suite and recomputation results and the
isolated Python dependency snapshot used for the passing checks.

The [historical verification amendment](amendment-2026-11-15-verification.md) allows
verification from later main revisions. It rebuilds the registered `base_commit`
`6e61ee4` in a disposable local checkout and restores the exact original OOS runner
from the recorded execution commit `d1c4865`. Its original provenance checks still
cover all ten calculation modules, the original metric definitions and calendar,
all original runner sources, data hashes and every result. Current main's code is
free to change; it is never substituted into this historical calculation.

## Local verification

With the original `data/external/` directory present and the repository's backend
requirements installed:

```sh
cd backend
python -m pytest -q
python -m storm.oos.run --verify
```

Verification is read-only, makes no network requests, checks all raw, diagnostic,
compressed-feed and parquet hashes, recomputes every metric and policy result, and
compares exact JSON values as well as deterministic Markdown. A missing or changed
artifact fails verification. Tests require no external data or network; the Markdown
test checks the entire JSON through its rendered content digest, including provenance.

The local Git object database must contain both recorded revisions and the registration
history (retain the OOS branch/history when cloning). Missing history is an error, with
no fallback to current main. The temporary checkout is removed afterwards and does
not change the caller's files, index, refs or worktree registration. Later amendments
are not inserted retroactively into the original results' provenance.

Exact runtime fingerprints also require CPython 3.10.0, NumPy 2.2.6, pandas 2.3.3 and
PyArrow 24.0.0, as recorded in the original execution. Under other versions, only the
runtime-sensitive frozen-core pytest tests skip with the registered/running version
differences; the rest of the suite still runs. `--verify` remains strict. See the
[runtime amendment](amendment-2026-11-15-runtime.md) for the compatibility rule.

From another checkout, point at the existing original acquisition directory:

```sh
python -m storm.oos.run --verify --data-dir /path/to/original/data/external
```

`results.json` holds exact and display-rounded results. `results.md` is generated from
that JSON and may not be manually edited. The marker `run_started.json` prevents an
accidental second primary evaluation, even if a run fails before writing results.

## Acquisition in a fresh checkout

Do not reacquire over the original dataset. A fresh acquisition produces different
diagnostic timestamps and might receive revised vendor candles, so it is a replication,
not byte-identical verification. The acquisition command requires the pinned npm package:

```sh
npm install --prefix /private/tmp/stormscore-oos-downloader --ignore-scripts --no-audit --no-fund --save-exact dukascopy-node@1.46.4
cd backend
python -m storm.oos.acquire --cli /private/tmp/stormscore-oos-downloader/node_modules/.bin/dukascopy-node
```

Before acquisition, exclude `/data/external/` in the checkout's Git local exclude file.
This lane does not modify the shared `.gitignore` or requirements file. No market data
are committed. The only extra installed tool is the pinned npm acquisition package;
Python uses the existing backend dependencies. The implementation retains source
`.bi5` bodies, separate bid/ask CSVs, per-request HTTP statuses, quality/gap reports,
ingest-compatible per-pair parquet files and the acquisition manifest.

## Interpretation

This is a frozen historical holdout against another vendor and periods outside the
SGX July/August training/evaluation data. The famous storms were chosen by name, so
their detection rate is a stress-case result; ordinary months provide the separate
false-alarm sample. It is not evidence of prospective price prediction.

The unchanged core supports USD pairs directly. A documented OOS adapter reuses the
same price-only feature and label calculations for EURCHF and AUDJPY and discards the
surrogate USD sign/conversion fields. Comove is inert under the frozen zero weight.
No USD policy valuation is claimed for these two crosses. Supported-pair policy
books are synthetic, reset independently at each window, and show next-bar bid/ask
fills and margin calls. Cross support in the shared exposure engine would be a
separate backend/contract change outside this lane.
