# Final round-two conversion from retained responses

Recorded before the first scored run. The partial-artifact amendment makes source
availability an artifact-level question and keeps the original monthly coverage rules.
The pinned CLI writes CSVs in batches; a side's 600-second limit can leave successful
raw response bodies in its cache that have not yet reached the incremental CSV.

After the chronological acquisition manifest closes, perform one network-free final
conversion from all successful retained bodies for selected months. Use the exact
pinned package's exported processData with volume enabled and zero-volume flats
excluded, as in registration 1's documented conversion correction. Dates, instruments,
quote sides, price normalization and structural tests are unchanged. Each missing
daily body remains missing; no interpolation or another request occurs. Failed
decoder/structural/coverage checks still make the pair-month unusable.

Preserve the original incremental CSVs and any initial parquets. Write decoded CSVs
separately and require every overlapping timestamp/OHLC field to equal the original
CLI output exactly. Record saved and missing daily counts per side, source decoder
hash, overlap check count and zero new network requests. Keep the original acquisition
status/reason alongside final conversion status. The source-attempt completion times
and chronological selected prefix are unchanged by this conversion.

This is the mechanical implementation of the registered partial-month threshold,
not a change in coverage, detector, label, policy or selected dates. All available
artifacts are converted blindly before any detector result is computed. The original
manifest, every failure log and all raw response bodies remain in the hash inventory.
