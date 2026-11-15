# Censoring clarification — 15 November 2026

Written after registration and before any statistical calculation. The registration's
phrase “closed/open status” is imprecise for a right-censored episode translated away
from the right edge. Preserve the recorded censoring flag in audit rows, but use its
observed clock duration through the evaluation end as its finite duration for both real
and randomized matching/actions. A translated censored endpoint is administrative, not
an inferred all-clear: it schedules no restore, just as the original open alarm did not.
Closed episodes retain a real all-clear and schedule restoration. Real matching before
the evaluation end is unchanged. Require observed finite-risk alarm starts and observed
closed endpoints; the administrative endpoint of an open episode need not be an
observed bar, but must not cross the window end. Offset zero must remain feasible.

For round two, retain the experiment's independent supported weekly books and carry-in
alarm convention, rather than introducing a year-long book. Translate the annual train
once per pair and apply the same offsets to every registered usable week; create a
carry-in cut at a week's first bar if a shifted danger episode was already active there.
This preserves the registered reset design and the number/durations of annual alarms.
Policy inference remains a new current-main secondary calculation.

A pair with no alarms has one effective timing configuration, offset zero. Its lack of
signals contributes zeros without making the other pairs' null degenerate. Report a
test as fully degenerate only if every contributing pair has one effective offset.
