# Acquisition implementation correction, before scoring

15 November 2026. No detector evaluation has started. All fourteen pair-windows were
downloaded from the frozen official feed. A pre-score completeness review found that
the converted files contained every calendar minute, including closed weekends.
Inspection of the pinned `dukascopy-node@1.46.4` decoder showed why: `ignoreFlats=true`
tests the sixth normalised field (volume), but the CLI's default `volumes=false` removes
that field before the filter. An undefined field is not zero, so the placeholders remain.

Correct the acquisition implementation to enforce the preregistered exclusion of
zero-volume candles: enable `-v`, and require volume metadata in the OOS reader, which
independently excludes zero-volume rows. No frozen rule changes. No price-magnitude
filter, interpolation or new market data. Re-decode the already saved `.bi5` bodies
locally using the exact pinned package's exported `processData`, with `volumes=true`
and `ignoreFlats=true`; do not download again. Preserve the first CSVs and parquets,
write filtered CSVs alongside them, and retain the original manifest. Require every
retained timestamp and OHLC price to equal its original downloaded candle exactly.

Rebuild the per-pair parquets and final manifest from the filtered bid/ask observations,
then reapply the original warm-up, completeness and structural validation rules. This
correction fixes the observed-day denominator and trailing-bar history in accordance
with the registration. All initial outputs and diagnostics remain in the hash inventory.
The first scored run will use only the corrected conversion. A regression test covers
zero-volume exclusion and refusal to accept source candles without volume metadata.
