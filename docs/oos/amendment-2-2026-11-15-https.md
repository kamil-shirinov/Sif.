# Registration 2 feed transport amendment — 15 November 2026

Before any scored round-two run, the network-authorised attempt using registration 1's
HTTP transport received HTTP 301 redirects to the same hostname/path over HTTPS. All
72 pair-month CSVs remained empty; no compressed feed artifacts were returned to that
acquisition. Its diagnostics and the earlier sandbox diagnostics will be preserved
inside `data/external/round2/http-redirect-attempt/` and hashed in final provenance.

The old HTTP endpoint had worked for registration 1. Current direct HTTPS probes of
the registered EURUSD 2 January 2025 daily artifact and the original EURCHF probe
returned HTTP 200 with binary bodies (11,756 and 8,494 bytes), after earlier transient
HTTPS errors. These probes established transport availability; no detector output or
policy performance has been computed or viewed.

Perform the final acquisition attempt using direct HTTPS to the exact original
datafeed hostname and artifact paths, with normal TLS certificate verification and
the unchanged pinned CLI/decoder. Use a round-two-only transport preload; do not alter
registration 1's source. Keep the 60-second socket timeout and three retries; pause ten
seconds between retries to avoid hammering transient failures. Use three pair jobs,
within the registered maximum of six, with the same five-request batches and one-second
batch pause. Retain response bodies, status/byte logs and all earlier failed attempts.

No vendor, pair, date, bar type, quality criterion, metric, detector parameter, weekly
policy convention or deadline changes. The registration remains immutable. Commit and
push this transport amendment before the final acquisition attempt. If source requests
still fail, report those pair-months unusable and never replace or retry them based on
detector outcomes. No additional acquisition attempt is authorised by this amendment.
