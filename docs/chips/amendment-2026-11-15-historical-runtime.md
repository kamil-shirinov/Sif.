# Historical core and runtime amendment — 15 November 2026

Added after the experiment at Kamil's request following a Python 3.12 fresh-venv
failure. The preregistration, results JSON and results Markdown remain byte for
byte unchanged from `eeab16c`. No download, detector run, relabelling, tuning,
model call, database write or replay change is part of this amendment.

The registered calculation base remains
`3625e41f019551720b4c0e3f860aa48c9652d801`. Ordinary tests must not demand that a
later main checkout still contains that revision's backend. Historical checks
now build that commit in a temporary local Git clone, restore only the maintained
strict checker and immutable preregistration, then execute the checker in a fresh
Python process. Every registered source hash is also checked directly against the
rebuilt files, independently of the running interpreter. No remote is fetched,
the caller's worktree/index/refs stay untouched, and the clone is removed afterwards.

The retained experiment environment used `~/.venvs/stormscore/bin/python`, CPython
3.10.0. Its numerical/storage library versions below match the original immutable
`results.json` acquisition provenance. The interpreter was observed in the retained
run environment; it was not recorded in the original results JSON, and this
amendment does not retrospectively add it there. The same acquisition provenance
also records yfinance 1.8.0; that downloader version is not part of the runtime
fingerprint gate because these checks neither import it nor acquire data.

| Component | Registered runtime |
| --- | --- |
| Implementation | CPython |
| Python | 3.10.0 |
| NumPy | 2.2.6 |
| pandas | 2.3.3 |
| PyArrow | 25.0.1 |

The machine-readable runtime for the historical pytest gate is:

```json
{
  "implementation": "CPython",
  "python": "3.10.0",
  "numpy": "2.2.6",
  "pandas": "2.3.3",
  "pyarrow": "25.0.1"
}
```

`storm.backtest.code_fingerprint()` includes runtime constants and imported
bindings as well as source bytes. A fresh installation of the ranged
`backend/requirements.txt` dependencies is therefore not an exact historical
runtime. Equality here includes interpreter/library patch versions; no operating
system restriction is added.

Only tests executing historical runtime fingerprints skip on an interpreter
implementation, Python version or listed library mismatch. The skip message
names each mismatch, points to this amendment, and explicitly states that it
does not verify the historical fingerprint. Immutable artifact, rebuilt source
byte, synthetic pipeline and report checks continue to run on newer runtimes.
No fingerprint exception is converted into a skip: under the registered runtime,
the rebuilt base must pass, and deliberate runtime constant changes and source
changes in the disposable core or AI module must fail. The existing operational
`check_frozen()` remains strict for new experiment execution; it is not weakened
to permit a new run against changed code.

Validation used the retained registered venv and a Python 3.12.13 venv installed
from `backend/requirements.txt` (NumPy 2.5.4, pandas 2.3.3, PyArrow 26.0.1).
`cd backend && python -m pytest -q` passed with 349 passed / 9 skipped on the
registered runtime and 345 passed / 13 skipped on Python 3.12. The four additional
skips are precisely the chips historical fingerprint and mutation checks. The
chips-only suite passed 17 tests on the registered runtime and 13 tests with
4 explicit skips on Python 3.12. A disposable caller with a committed later
detector change also rebuilt the old base successfully on both runtimes; source
and constant mutations inside the registered rebuild failed under the registered
runtime. The original preregistration and both result files were hash-checked
against their published bytes.
