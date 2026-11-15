# Feed transport amendment — 15 November 2026

Written after the unsuccessful HTTPS retry and before any detector evaluation. The
registration and first amendment remain unchanged. The longer-timeout HTTPS attempt
also failed for every planned pair-window, with feed errors; HTTPS probes returned 503,
connection resets or timeouts. A successful HTTPS probe of the original EURCHF URL did
not generalise to other artifacts. These failed attempts are not evidence that the
underlying historical candles do not exist.

Dukascopy's own `https://www.dukascopy.com/datafeed/...` returned HTTP 301 with Location
`http://datafeed.dukascopy.com/datafeed/...` for the identical EURUSD artifact. A request
to that official HTTP endpoint returned HTTP 200 and 10,739 bytes for the registered
1 March 2024 bid candle file, while its HTTPS equivalent failed. The HTTP endpoint uses
the same hostname and artifact paths; it is the same vendor/data, rather than a substitute.

Perform one additional acquisition attempt over that HTTP endpoint. Keep the exact
pinned package, decoder, URLs' paths, pairs, date ranges, price sides and quality rules.
The existing preload changes only the request scheme to HTTP, retaining a 60-second
socket timeout and the downloader's three retries. This transport does not provide TLS
authentication; record exact raw response SHA-256s for reproducibility. Store successful
`.bi5` bodies and per-request status/byte-count logs. Preserve the completely failed
HTTPS retry under `data/external/transport-attempt-2/`, alongside attempt 1.

No detector result has been viewed. No label, detector, threshold, scoring, book or
data-quality change is authorised by this amendment. Commit and push it before the
HTTP attempt. If that attempt cannot obtain valid data, retain and report unusable
datasets with the actual errors, without replacing an event or trying another vendor.
