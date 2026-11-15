# Transport amendment — 15 November 2026

Written after acquisition attempt 1 and before any detector evaluation. The original
preregistration is unchanged. Every requested pair-window failed acquisition with the
pinned Node CLI: its native fetch failed with `UND_ERR_CONNECT_TIMEOUT`, reporting a
10,000 ms connection timeout. A direct curl probe of the same registered EURCHF candle
URL returned HTTP 200 and 8,494 bytes; the initial header probe took about 18 seconds.
This is a transport failure, not evidence that these historical datasets are absent.

Retry acquisition once with the same `dukascopy-node@1.46.4` package and decoder, URLs,
instruments, bid/ask sides, bar timeframe, date ranges and flat-candle handling. A small
acquisition-only preload uses Node's built-in `https` transport with a 60-second socket
timeout in place of native fetch's 10-second connection limit. TLS remains verified.
The pinned downloader still controls exactly three retries per failed artifact. Preserve
the complete failed first attempt under `data/external/transport-attempt-1/`, and retain
the successful feed responses as `.bi5` under `data/external/feed-cache/` as well as the
CSV and parquet files. All retained files receive hashes in the final provenance.

No detector, label, threshold, data-quality criterion, metric, policy parameter, selected
event or scoring boundary changes. No detector result has been viewed. This amendment
and the preload source will be committed and pushed before the retry starts.
