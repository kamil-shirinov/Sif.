# Statistical evidence lane

The immutable [preregistration](preregistration.md) was committed and pushed alone
before analysis. [results.md](results.md) is rendered directly from
[results.json](results.json). These are secondary retrospective analyses of frozen
experiments; no detector or policy parameter is selected from these results.

Use the retained experiment environment (CPython 3.10.0, NumPy 2.2.6, pandas 2.3.3,
PyArrow 25.0.1) for exact runtime fingerprints:

```sh
cd backend
~/.venvs/stormscore/bin/python -m storm.stats.run
~/.venvs/stormscore/bin/python -m pytest -q
```

`--include-round2` includes the byte-exact remote results snapshot captured by
`python -m storm.stats.monitor`. The monitor fetches only `lane/cx-oos2` at
fifteen-minute intervals until results exist or 08:30 UTC on 15 November 2026
(extended from 07:45 by the explicit user instruction in the dated cutoff amendment);
`round2-polls.json` records checks, commits and artifact hashes. The run reads the
original data in the worktrees listed in the registration. It never acquires,
rewrites or commits market data.

`--resume` reuses only unit artifacts matching the complete calculation-source
and input hash inventory. Dataset/task/pair random streams have stable hash-derived
keys, so adding round two cannot change earlier draws. `--only-unit NAME` is an
auditable development check without publishing a partial aggregate.

Full detection/policy null arrays, exact sampled offsets, feasible-offset hashes,
alarm durations/censoring flags and per-storm hit arrays are in `nulls/`.
Per-storm records, observed day blocks, original/current policy results and every
sensitivity row are in `units/`. SVGs are standalone Matplotlib exports.

No production/shared files or dependency manifests are changed. The local analysis
uses already-installed Matplotlib for chart export; reproducing the SVG export
requires Matplotlib (3.10.9 in this environment). An optional local C++17 compiler
accelerates the path calculations and writes its compiled library only to a
temporary cache. Without it, calculations fall back to the unchanged Python
simulators. Every real and representative shuffled accelerated book is checked
against those simulators. No package installation is performed by the analysis.

Known limitations are part of the report: small/dependent event samples, selected
historical stress windows, previously seen chip dates, retrospective strongest-window
labels, the conditional timing null, quote-free chip bars, and synthetic reset books.
Sensitivity is one factor at a time; it never replaces the frozen headline.
