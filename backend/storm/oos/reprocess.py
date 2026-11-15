"""Enforce the registered flat exclusion on saved feed bodies, without network access."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import pandas as pd

from .acquire import OHLC, convert
from .protocol import DATA, DOCS, check_frozen, sha256


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package-dir", type=Path, required=True)
    args = ap.parse_args()
    spec = check_frozen()
    if (DOCS / "run_started.json").exists() or (DOCS / "results.json").exists():
        raise SystemExit("a scored run has started; reconversion refused")
    manifest_path = DATA / "manifest.json"
    archive = DATA / "manifest-before-flat-exclusion.json"
    if archive.exists():
        raise SystemExit("reconversion already attempted; refusing another")
    manifest = json.loads(manifest_path.read_text())
    shutil.copy2(manifest_path, archive)
    command = ["node", str(Path(__file__).with_name("decode.cjs")),
               str(args.package_dir.resolve()), str(manifest_path)]
    with (DATA / "flat-exclusion.log").open("w") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)
    windows = {w["id"]: w for w in spec["windows"]}
    for window in manifest["windows"]:
        for record in window["pairs"]:
            record["unfiltered_raw"] = record["raw"]
            filtered_raw = {}
            for side, original in record["raw"].items():
                path = DATA / original["path"]
                filtered = path.with_stem(path.stem + "_filtered")
                old = pd.read_csv(path).set_index("timestamp")[list(OHLC)]
                new = pd.read_csv(filtered).set_index("timestamp")[list(OHLC)]
                pd.testing.assert_frame_equal(new, old.reindex(new.index), check_exact=True)
                filtered_raw[side] = {"path": str(filtered.relative_to(DATA)), "sha256": sha256(filtered)}
            record["raw"] = filtered_raw
            output = DATA / record["parquet"]["path"]
            old_output = output.parent.with_name("processed-with-flats") / output.name
            old_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(output), str(old_output))
            record["unfiltered_parquet"] = {"path": str(old_output.relative_to(DATA)), "sha256": sha256(old_output)}
            try:
                record["quality"] = convert(DATA / record["raw"]["bid"]["path"],
                                            DATA / record["raw"]["ask"]["path"], windows[window["id"]], output)
                record["parquet"] = {"path": str(output.relative_to(DATA)), "sha256": sha256(output)}
                record["status"], record["reason"] = "usable", None
            except (ValueError, KeyError, OSError) as exc:
                record.pop("parquet", None)
                record.pop("quality", None)
                record["status"], record["reason"] = "unusable", str(exc)
            print(window["id"], record["pair"], record["status"], record["reason"] or "")
    manifest["flat_exclusion_correction"] = {
        "utc": pd.Timestamp.now(tz="UTC").isoformat(), "before_first_detector_run": True,
        "note_sha256": sha256(DOCS / "acquisition_notes.md"),
        "decoder_cli_sha256": sha256(args.package_dir / "dist" / "cli" / "index.js"),
        "decoder_api_sha256": sha256(args.package_dir / "dist" / "index.js"),
        "npm_lock_sha256": sha256(args.package_dir.parent.parent / "package-lock.json"),
        "retained_prices_exactly_equal": True, "network_requests": 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
