# Historical verification amendment — 15 November 2026

Added after the primary scored run and publication of its results at `9b34226`, at
Kamil's explicit request. The preregistration, primary-run marker, results JSON and
results Markdown remain byte-for-byte unchanged. No new primary detector run,
threshold change, relabelling, data acquisition, event replacement or policy change.

CC-L's window fix changes `exposure.py`, `export.py`, `equity.py` and `docs/metrics.md`
on main. These legitimate later changes must not change this historical study or
make main's ordinary pytest suite fail merely because it no longer matches an old
code fingerprint. The registered calculation revision remains exactly
`6e61ee4311d4c18c19def5d8b573d0fb67791ee0`.

Replace the rule that verification compares the caller's current core and all current
OOS source files with the historical provenance. Instead, `storm.oos.run --verify`
rebuilds `base_commit` in a disposable local Git checkout, then restores the original
OOS runner from the execution record's `wrapper_commit_at_run` (`d1c4865`). It checks
that runner's source hashes, shares the existing acquisition directory through a
directory link, and invokes the original read-only verification in a fresh process.
That process must still match every original core fingerprint, config/calendar/metric
definition hash, acquisition-file hash, exact result, rounded result and Markdown.

The disposable checkout uses only local Git objects, with no fetch, download or shared
worktree/index/ref mutation, and is removed afterwards. Missing history, changed input
artifacts or mismatched results remain errors; there is no fallback to current main.
The original recorded amendments and acquisition notes are still checked. This later
verification amendment is not retroactively inserted into the first run's provenance.

Pytest checks the immutable registration and recorded result artifacts in the caller,
and checks the historical core fingerprint and rejection of patched constants inside
the rebuilt registered checkout. It does not demand that today's backend source or
metric definitions still equal the old files. Synthetic adapter/aggregation tests may
continue to exercise today's public interfaces. An optional `--data-dir` locates the
unchanged original acquisition directory when verifying from a different checkout.
