"""Re-score archived outputs without downloading, retuning or rerunning a detector."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from storm.evaluate import score

from .protocol import DATA, DOCS, check_frozen, sha256


def verify(data: Path = DATA) -> dict:
    check_frozen()
    result = json.loads((DOCS / "results.json").read_text())
    acquired = result["acquisition"]["tickers"]
    feats = {}
    for ticker, info in acquired.items():
        if info["status"] != "acquired":
            continue
        path = data / info["file"]
        assert sha256(path) == info["sha256"], ticker
        raw = pd.read_parquet(path)
        assert len(raw) == info["rows"]
        frame = pd.read_parquet(data / f"{ticker}_features.parquet")
        pd.testing.assert_series_equal(frame.mid, raw.set_index("timestamp").close.reindex(frame.index),
                                       check_names=False, check_freq=False)
        feats[ticker] = frame
    storms = pd.DataFrame(result["storms"])
    for col in ("onset_utc", "trough_utc", "end_utc", "event_utc", "first_onset_utc"):
        storms[col] = pd.to_datetime(storms[col], utc=True)
    storms = storms.sort_values(["onset_utc", "pair"]).reset_index(drop=True)
    for name, tickers in {"new_tickers": [s for s in feats if s != "NVDA"], "nvda_in_sample": ["NVDA"],
                          "all_descriptive": list(feats)}.items():
        alarms = {s: [(pd.Timestamp(a["alarm_utc"]), None if a["clear_utc"] is None else pd.Timestamp(a["clear_utc"]))
                      for a in result["detections"] if a["ticker"] == s] for s in tickers}
        expected = result["pooled"][name]
        actual = score(alarms, storms[storms.pair.isin(tickers)], {s: feats[s].mid for s in tickers},
                       expected["trading_days"])
        for key, value in actual.items():
            if key == "squalls_per_day":
                continue  # squall-only episodes are not a storm-level alarm archive
            assert expected[key] == value, (name, key)
    return {"raw_hashes_verified": len(feats), "pooled_scores_reproduced": 3,
            "detector_reruns": 0, "network_requests": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
