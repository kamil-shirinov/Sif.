# Registration 2 partial-artifact handling — 15 November 2026

Written before the first scored run. The HTTPS acquisition received genuine candles,
but intermittent daily 503 responses exhausted the registered three retries. The pinned
CLI defaults to aborting a whole monthly export on one such failure, leaving later days
and the other quote side unattempted. Acquisition was paused; no detector or policy
result has been viewed. Preserve the interrupted HTTPS pass and all previous diagnostics.

Clarify/extend the original transport-failure rule: an exhausted **daily artifact** is
unusable and remains a missing interval; it need not invalidate an otherwise sufficiently
observed pair-month. Finish the existing acquisition using the pinned CLI's public
`--no-fail-after-retries` option, so it continues past unavailable daily artifacts. Retain
the original 50% observed weekday-minute monthly threshold, 720 initial joined warm-up
bars and every structural quote validation. Partial months meeting those exact original
thresholds are usable and explicitly identified by their actual coverage, gaps and
failed daily-artifact diagnostics. Do not interpolate, invent quotes or retry based on
the size/direction of a move. This rule is fixed before any scored result.

This is a bounded continuation, not another full network retry. Reuse only successful
raw bodies from this same round-two acquisition. For a previously started CLI batch,
every artifact lacking a successful saved body is conservatively deemed exhausted,
even if fewer attempts may actually have occurred. Reconstruct attempted batches from
the deterministic five-day batch order and the retained status logs, conservatively
including the whole last observed batch (or first batch if no response was logged).
Write the complete exhausted-URL list, never make another network request for any such
URL, and retain its absence. Completed raw bodies come from a local content cache;
only previously unattempted artifacts receive the original initial request plus three
retries. Log cache hits and cached failures separately from actual network responses.

The continuation visits all six pairs and January through December in the same fixed
order, retaining the original deadline/prefix rule. No vendor, pair, date range,
detector/config, label, policy, coverage threshold or outcome definition changes.
The no-additional-acquisition rule in the HTTPS amendment is superseded only to allow
this bounded completion of unattempted artifacts, with no further requests for exhausted
ones. Commit and push this amendment before continuing. The original registration and
all failed/partial outputs remain unchanged in the audit record.
