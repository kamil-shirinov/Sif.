# Chip-sector experiment

The protocol was pushed in its own commit before downloading. Read
[preregistration.md](preregistration.md) and [results.md](results.md); exact values,
request outcomes and fingerprints are in [results.json](results.json).

The worktree is `/private/tmp/stormscore-cx-chips`, branch `lane/cx-chips`, based on
main `3625e41`. Only the three assigned lane directories are changed. Shared
`storm.equity`, `storm.export`, `storm.live` and `storm.ai` sources remain frozen.
No shared dependency or contract change is needed. The already-installed Modal
deployment SDK remains an optional dependency for the private experiment.

The primary window is every served bar from the registered thirty-calendar-day
probe. Yahoo returned twenty trading dates, October 19 through November 13,
rather than only the approximate seven expected. The results also contain the
requested November 9–13 view, computed from the archived run without restarting
the detector. The three replays are the registered largest absolute moves in the
full served window; they therefore occur in October. An upward move and misses
are intentionally retained.

Local data and intermediate frames are in `data/processed/chips/` in this
worktree and are ignored. The three completed replays are also in the main
checkout's `web/public/bundles/`, appended after its existing entries. They use
the default GLM/Kimi reports; the private reports and audits are retained here
as synthetic-book evidence. No data or bundle is committed.

Commands used, with the existing `~/.venvs/stormscore/bin/python` environment
and `PYTHONPATH=backend` from the worktree root:

```sh
python -m storm.chips.acquire
python -m storm.chips.evaluate
STORM_ENV_FILE=~/Desktop/stormscore/.env python -m storm.chips.tiger
python -m storm.chips.replay
python -m storm.chips.crew
python -m storm.chips.crew --private
python -m storm.chips.replay --publish
python -m storm.chips.modal_audit
python -m storm.chips.report
python -m storm.chips.verify
cd backend
python -m pytest -q
```

Acquisition, evaluation and crew commands refuse to overwrite their original
run records. They are an execution record, not instructions to repeat a primary
experiment against today's changed retention window. `storm.chips.verify` checks
the local raw hashes and reproduces pooled scoring from archived detections and
features without new downloads or detector runs. Backend tests are offline.

`storm.chips.replay` creates an isolated function namespace for the existing
equity builder. It binds symbol, synthetic book and selected label facts without
changing the source or globals. The fifteen-minute label's close-price extrema
replace NVDA's demonstration-specific overnight close/low; actual bar OHLC and
the frozen book simulation remain intact. Stress labels are recomputed only on
history available at the exposure snapshot, with future reversals unavailable.
The internal `USD_` label adapter only resolves the shared label module's USD
sign dispatcher; it is removed from every returned equity row.

The Fireworks task guard uses its existing $10 task cap and global caps without
manual ledger edits. Modal has a watchdog, explicit finally-stop, server-confirmed
stopped state with zero tasks, complete-bucket allocation evidence, and a
conservative runtime cost estimate including termination. Token accounting is
separate from runtime and no estimate is described as an invoice.
