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
Reproduce from this frozen checkout: later changes to the backend or metric definitions
must not be presented as this same registered evaluation. The branch has not been
rebased onto concurrent backend fixes. The unchanged USD policy engine cannot value
EURCHF or AUDJPY without extra conversion data, so their policy results are explicitly
unsupported while all their price-only detection metrics remain included.
