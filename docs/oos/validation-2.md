# Registration 2 validation — 15 November 2026

The single primary evaluation started at `2026-11-15T07:01:41.121442+00:00` and finished at
`2026-11-15T07:01:50.507192+00:00`, using committed runner `3b271272f9c34f8a1f138dece4ae2b011edd0560` and
frozen main `3625e41f019551720b4c0e3f860aa48c9652d801`. The preregistration was pushed alone at
`5f39e4562e4d0b082655e9ce43d583bc4647fd0c` before acquisition. Its bytes and all registration-1
published artifacts remain unchanged.

The original acquisition cutoffs were applied: no new month from 06:55 UTC, hard stop
07:05 UTC. January–July form the completed chronological prefix; August–December are
explicitly not completed by deadline. The later user extension to 08:30 UK delivery was
received after the queued primary run had completed; acquisition was not extended and
the primary evaluation was not restarted. No deadline or evaluation rule changed.

[Results Markdown](results-2.md) and [exact JSON](results-2.json) include all 72 planned
pair-months and all 318 planned pair-weeks. There are 24 usable pair-months,
38 labelled storms, 32 alarmed storms, 10 caught with at least half the move ahead,
and 28 primary misses. The four initially eligible pairs are EURUSD, USDJPY, USDSGD
and USDCHF; GBPUSD and AUDUSD remain unassessed because their December warm-up failed
the registered rule. Missing intervals can conceal additional storms. The planned June
overlap with registration 1 is disclosed; it is not newly unseen evidence.

The independent synthetic weekly books have 98 usable pair-weeks: 13 helped,
23 hurt and 62 ties. The median weekly difference is $0.00; the summed
difference is $-477,176.99, after the frozen engine's spread costs. There are
1 avoided margin calls, 0 induced calls and 9 weeks with both books called.
These are independent $1M-equity reset books, not one continuous portfolio return.

Validation completed under CPython 3.10.0, NumPy 2.2.6, pandas 2.3.3,
and PyArrow 24.0.0:

- `cd backend && python -m pytest -q`: **356 passed, 6 skipped**.
- `python -m storm.oos.run --verify`: both registrations passed after the primary run.
- A second combined verification using the persistent archived data paths below passed;
  each verifier rebuilt its own registered base and original committed OOS wrapper, and
  matched exact results, Markdown, weekly fills and every input/source hash.
- Python 3.12.13 OOS portability preflight: **49 passed, 3 skipped, 1 deselected**;
  only the not-yet-created round-two results consistency test was deselected at that time.
  The three runtime-sensitive fingerprint checks skipped with explicit registered/running
  version differences. The results consistency test passed in the final registered suite.

Persistent local data copies (gitignored, never committed):

```text
/Users/kamilshirinov/Desktop/stormscore/data/external/round1/
/Users/kamilshirinov/Desktop/stormscore/data/external/round2/
```

The round-one archive has 723 byte-identical files. All 2956 round-two files in both
the working and archived inventories exactly match the published SHA-256 map. With this
layout, the combined verifier uses the default paths after merge. Alternative paths:

```sh
cd backend
python -m storm.oos.run --verify \
  --data-dir /Users/kamilshirinov/Desktop/stormscore/data/external/round1 \
  --round-two-data-dir /Users/kamilshirinov/Desktop/stormscore/data/external/round2
```

No data files, dependency files, shared contracts or another lane's modules were committed.
