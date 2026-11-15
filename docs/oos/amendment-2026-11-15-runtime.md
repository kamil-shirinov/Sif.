# Frozen-runtime test portability amendment — 15 November 2026

Added after the primary scored run and historical-verification amendment, at Kamil's
request following a Python 3.12 fresh-venv failure. The registration, original runner,
results, data, thresholds and all original provenance hashes remain unchanged.

The primary run's `results.json` execution record establishes these exact versions:

| Component | Registered runtime |
| --- | --- |
| Interpreter | CPython 3.10.0 |
| NumPy | 2.2.6 |
| pandas | 2.3.3 |
| PyArrow | 24.0.0 |

The interpreter implementation was CPython, confirmed in the retained run environment.
The three library versions and Python version are recorded in the immutable execution
record. The broader passing test environment is in `validation-environment.txt`; this
amendment does not retrospectively claim that snapshot describes every package in the
original primary-run environment. Python, implementation and library version equality
here is exact, including patch versions. The recorded platform was Darwin; this change
does not add an operating-system restriction.

`storm.backtest.code_fingerprint()` includes runtime constants and imported bindings
as well as source bytes. Consequently, a restored source tree under a different Python
or numerical-library runtime can produce a different fingerprint. A freshly installed
`backend/requirements.txt` is not an exact reproduction of the registered runtime.

The pytest tests that execute historical runtime fingerprints now skip before building
the snapshot when the interpreter implementation/version or any listed library differs.
The skip message identifies each mismatched component with its registered and running
version, links to this amendment and states that a skip does not verify the fingerprint.
Immutable artifact checks, source-byte checks, synthetic pipeline tests, report checks
and other backend tests remain active under newer runtimes.

Under the registered versions, the original fingerprint comparison remains strict:
a genuine mismatch fails. Tests deliberately patch a constant and change a source file
inside disposable registered checkouts to prove that code drift is still rejected.
No fingerprint mismatch is caught and converted into a skip. The `--verify` command
remains strict and continues using the rebuilt base and original recorded runner;
it must be run under the registered runtime for exact historical verification.
