# Registration 2 independent warm-up clarification — 15 November 2026

Before the first scored run, a temporary January conversion audit showed that valid
December warm-up quotes can exist even when January's evaluation coverage fails the
fixed 50% threshold. The initial loader would discard that valid December history
with the failed January file, thereby discarding later usable months for the pair.
No detector or policy outcome has been viewed; the threshold is not being relaxed.

Clarify the separate eligibility rules: validate the registered 27–31 December 2024
warm-up interval independently, with exactly the same timestamp/OHLC/spread/volume
checks and at least 720 joined observed bars. Preserve it as a separate warm-up parquet,
including when January 2025 is unusable for evaluation. A pair's usable later months
may then use that genuinely observed earlier history; the failed January remains a
gap and never contributes bars, labels, alarms, observed days or weekly-book marks.
Pairs without the required valid December warm-up remain unavailable, without a
substitute interval or new download. If January is usable, do not duplicate its warm-up.

Monthly 50% coverage, weekly eligibility, all pair/date choices, source request budgets,
detector, label, policy and deadline rules are unchanged. All extraction is from the
same retained raw bodies with no network. Record the warm-up file/hash and its own
status separately from January's status. Commit this clarification before the first
scored run. The original preregistration remains byte-for-byte unchanged.
