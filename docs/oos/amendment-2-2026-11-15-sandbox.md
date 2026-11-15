# Registration 2 acquisition setup amendment — 15 November 2026

Before any round-two feed response or scored detector run, the initial acquisition was
accidentally launched in the network-restricted execution sandbox. All 72 pair-month
attempts failed DNS with `getaddrinfo ENOTFOUND datafeed.dukascopy.com`; their CSVs are
empty and no HTTP response/status files or compressed feed bodies were received.
This is an execution-permission failure, not evidence that those source periods are
unusable. It is not a basis for selecting or dropping any market period.

Preserve the entire failed attempt inside `data/external/round2/sandbox-attempt-1/`.
Retry the identical full chronological plan with authorised network access, still using
the same pinned package, HTTP transport, three per-artifact retries, date ranges,
instruments, quality rules and deadline. No additional retry based on detector or
policy results is authorised. Hash all archived setup diagnostics in final provenance.
This amendment is committed and pushed before that retry; the preregistration remains
unchanged and no detector outcome has been viewed.
