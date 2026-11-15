# Pooled duplicate accounting — 15 November 2026

Written after the first three-dataset report and before round-two results are
available on its remote branch. The first report has no source/time/pair overlap.
This specifies the already registered duplicate-removal rule for a possible
round-two overlap; no individual-dataset result or headline parameter changes.

Process datasets in fixed priority SGX, round one, round two, chips. A duplicate
observation is the same source, instrument and UTC minute already observed in a
higher-priority dataset. Only scored observations enter this comparison; warm-up
history is not a second scored sample. Keep original labels and alarms for every
individual dataset. In pooled summaries, exclude lower-priority storms whose
onset minute is a duplicate and exclude lower-priority alarm/false-episode starts
at duplicate minutes. Use original full-history matching/false classification,
then resample the retained storm rows and retained daily union-minute exposure.
Rebuild anchored false episodes after filtering alarm starts. Never relabel the
gapped residual history or call a previously true alarm false solely because its
storm was assigned to the higher-priority sample. Retain each surviving storm's
original matching result and original timing-null hit vector.

For pooled policy, conservatively exclude an entire lower-priority independent
reset book if any scored source/instrument/minute within that book duplicates a
higher-priority observation. Do not splice or partially reset it at an overlap
boundary. Individual-dataset policy totals keep every registered usable book.
Store per-book null arrays, retained/excluded book flags, duplicate bar/storm
counts, and both dataset and pooled contributions so the pooled statistic and
its null can be reconstructed. Apply the same retained observation/storm/book
sets to each sensitivity setting; price history and labels stay frozen.

The pooled date bootstrap groups by dataset and independent window just as before;
duplicate removal affects contributions, not the random timing null generated on
an original full dataset. Pooled inference remains descriptive. Report exposure
and reset-book exclusions explicitly, including zero exclusions when no overlap
exists.
