# Round-two publication cutoff extension — 15 November 2026

Recorded at 07:18 UTC after Kamil's explicit instruction following a usage reset:
include round two if origin/lane/cx-oos2 publishes docs/oos/results-2.json by
08:30 UK time; otherwise finalise without it, pushing by 08:45 UK at the latest.
UK time is UTC on this date. The original immutable registration said 07:45 UTC;
this user-authorized amendment extends only artifact availability monitoring.
No detector/policy setting, dataset selection rule, estimand, seed, bootstrap,
null or sensitivity changes. Round two has not been analysed in this lane;
the latest completed remote check at 07:06 UTC found no results document.

Continue fifteen-minute checks, with a final check at 08:30. Retain the original
poll log, capture the first published artifact byte-for-byte with its remote
commit and hash, and apply all existing provenance and pooled-duplicate checks.
If it is absent at the extended cutoff, report unavailable, not zero storms.

```json
{
  "amended_at_utc": "2026-11-15T07:18:00+00:00",
  "original_round2_cutoff_utc": "2026-11-15T07:45:00+00:00",
  "effective_round2_cutoff_utc": "2026-11-15T08:30:00+00:00",
  "finish_by_utc": "2026-11-15T08:45:00+00:00",
  "authorization": "Explicit user instruction after usage reset"
}
```
