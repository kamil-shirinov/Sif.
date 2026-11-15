# Validation — 15 November 2026

The primary scored run used the committed OOS implementation at `d1c4865` and the
registered core revision `6e61ee4311d4c18c19def5d8b573d0fb67791ee0`. The registration
was committed and pushed alone at `a849bfe` before acquisition. Its bytes remain
unchanged. The saved one-shot marker and results execution record identify the run.

Final checks in a fully isolated Python 3.10 virtual environment:

```text
python -m pytest -q
300 passed, 6 skipped, 1 warning

python -m storm.oos.run --verify
Verified: all results, data hashes, frozen config/code and Markdown match.
```

The suite's warning is Starlette's deprecation notice about its HTTP test client.
The original environment lacked declared FastAPI/psycopg dependencies and inherited
an undeclared global `httpx2` package. Existing AI tests prefer that module when it is
installed, but the OpenAI SDK expects an `httpx.Client`, so ten tests failed there.
Creating an environment without system site packages resolved that mismatch without
changing another lane's code. [validation-environment.txt](validation-environment.txt)
records the passing environment. NumPy 2.2.6, pandas 2.3.3 and PyArrow 24.0.0 match the
primary run. No requirements or shared files were edited, and no live model call ran.

Verification also passed in the original numerical environment. PyArrow printed
sandbox warnings about unavailable CPU-cache sysctl queries; it read all parquets and
the command exited successfully. There were no numerical or provenance mismatches.

All fourteen planned pair-windows passed the preregistered final quality checks.
The results retain 23 labels, including incidental storms in the ordinary months.
All 723 acquisition artifacts, including failed transport attempts and pre-correction
outputs, are hashed. Raw data remain local under `data/external/` and are not tracked.
The local exclude file handles this directory; the shared `.gitignore` is unchanged.

The frozen code fingerprint deliberately covers all ten core provenance modules.
The original run used this frozen checkout, before concurrent backend fixes. The
[historical verification amendment](amendment-2026-11-15-verification.md) subsequently
allows the command to rebuild that exact checkout when called from newer main, instead
of requiring current main to retain its old source or metric definitions. The original
results and registration remain unchanged. The unchanged USD policy engine cannot value
EURCHF or AUDJPY without extra conversion data, so their policy results are explicitly
unsupported while all their price-only detection metrics remain included.

## Verification after the window-fix merge

The historical verifier was subsequently tested in a disposable integration checkout
combining the OOS branch with main `5c4154625a7c3885ba7f2754c8eb3eaa5b1bd540`
(CC-L window-fix merge). Its `exposure.py`, `export.py`, `equity.py` and metric definitions
came from that newer main, while the verifier rebuilt the registered base for computation.

```text
python -m pytest -q
312 passed, 6 skipped, 1 warning

python -m storm.oos.run --verify --data-dir /path/to/original/data/external
Rebuilt registered base 6e61ee4311d4c18c19def5d8b573d0fb67791ee0 with recorded runner d1c486559d5a8547d1e46ba4b9d66b63e85a6267
Verified: all results, data hashes, frozen config/code and Markdown match.
```

The OOS-only tests also passed (26 tests). They check immutable published artifacts,
the rebuilt core and runner hashes, rejection of patched historical constants,
missing original data, and temporary-checkout cleanup. Their registration guard no
longer requires the caller's current core or metric definitions to equal the old ones.
No new primary run was performed. `preregistration.md`, `results.json`, `results.md`
and `run_started.json` are byte-for-byte identical to the published `9b34226` artifacts.

## Runtime portability check

The [runtime amendment](amendment-2026-11-15-runtime.md) records CPython 3.10.0,
NumPy 2.2.6, pandas 2.3.3 and PyArrow 24.0.0 as the exact historical runtime.
After adding the test-only version guard, the whole backend suite on this OOS branch
passed with **314 passed, 6 skipped** under those versions. The fingerprint tests ran,
including deliberate constant and source changes that were correctly rejected.

A fresh CPython 3.12.13 venv installed only `backend/requirements.txt` and resolved
NumPy 2.5.4, pandas 2.3.3 and PyArrow 26.0.1. Its whole suite passed with **311 passed,
9 skipped**. The three additional skips were exclusively the historical runtime
fingerprint tests; each reported the registered/running differences. Artifact,
source-byte, report, pipeline and other backend checks remained active. No production
verification or calculation code, dependency requirement or published artifact changed.
