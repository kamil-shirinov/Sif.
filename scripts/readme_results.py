"""Read the numbers in README.md's results tables and check them against metrics.json.

A results table in the README is preceded by a marker line

    <!-- metrics-table: methods.{col}. -->

A marker may name another reference file in square brackets, and the table is then checked against it
(`oos1` = docs/oos/results.json, `oos2` = docs/oos/results-2.json, `chips` = docs/chips/results.json):

    <!-- metrics-table[oos1]: display.totals.{col}.metrics. -->

Those references are rounded for display in the README, so a cell is compared with the reference value rounded
to the cell's own number of decimals (a cell "25.2" stands for 25.2058...).

and is an ordinary Markdown table whose header names the value columns in backticks, e.g.
`v1` and `naive`, and whose first column holds the metric's name in backticks, e.g. `caught`.
A cell's metric path is the marker's prefix, with {col} replaced by the column's name, followed by
the row's metric name: here `methods.v1.caught`. Any column whose header is not in backticks
(units, a plain-words meaning) is ignored. A value cell may carry $, commas, %, + or spaces; they
are dropped before comparing, so `$1,033,659` stands for 1033659.

    python scripts/readme_results.py --write-snapshot     # docs/results_snapshot.json from metrics.json
    python scripts/readme_results.py                      # print the check

The snapshot holds only the values the README cites, so the check still runs on a machine
without SGX's data (data/processed is not committed). Whenever metrics.json is present it is
the reference, and the snapshot is checked against it as well.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
METRICS = ROOT / "data" / "processed" / "metrics.json"
SNAPSHOT = ROOT / "docs" / "results_snapshot.json"

MARKER = re.compile(r"^<!--\s*metrics-table(?:\[(\w+)\])?:\s*(.*?)\s*-->\s*$")
EXTRA_SOURCES = {
    "oos1": ROOT / "docs" / "oos" / "results.json",
    "oos2": ROOT / "docs" / "oos" / "results-2.json",
    "chips": ROOT / "docs" / "chips" / "results.json",
}
CODE = re.compile(r"^`([^`]+)`$")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_tables(text: str) -> list[tuple[str, int, str, float | None]]:
    """(path, line number, cell text, number) for every value cell of every marked table."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = MARKER.match(lines[i])
        i += 1
        if not m:
            continue
        source = m.group(1)
        prefix = (f"{source}::" if source else "") + m.group(2)
        if i >= len(lines) or not lines[i].lstrip().startswith("|"):
            raise ValueError(f"line {i}: a metrics-table marker must be followed by a table")
        header = _cells(lines[i])
        cols = {k: CODE.match(h).group(1) for k, h in enumerate(header) if k > 0 and CODE.match(h)}
        if not cols:
            raise ValueError(f"line {i + 1}: the table has no backticked value column")
        i += 2  # header and the |---| line
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            cells = _cells(lines[i])
            name = CODE.match(cells[0]) if cells else None
            if not name:
                raise ValueError(f"line {i + 1}: the first cell must be a backticked metric name, got {cells[:1]}")
            for k, col in cols.items():
                cell = cells[k] if k < len(cells) else ""
                out.append((prefix.replace("{col}", col) + name.group(1), i + 1, cell, to_number(cell)))
            i += 1
    return out


def to_number(cell: str) -> float | None:
    s = re.sub(r"[\s$,%+]", "", cell.replace("−", "-"))
    try:
        return float(s)
    except ValueError:
        return None


def decimals(cell: str) -> int:
    """Digits after the decimal point in a cell, 0 for an integer ("$1,033,659" has none)."""
    m = re.search(r"\.(\d+)", cell)
    return len(m.group(1)) if m else 0


def lookup(metrics: dict, path: str):
    node = metrics
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


def _reference_for(path: str, reference: dict, extra: dict[str, dict] | None, flat: bool):
    """(value, rounded?) for a table path: `source::path` goes to that source's file, else to the metrics."""
    if "::" in path:
        source, inner = path.split("::", 1)
        if flat:
            return reference[path], True
        if extra is None or source not in extra:
            raise KeyError(path)
        return lookup(extra[source], inner), True
    return (reference[path] if flat else lookup(reference, path)), False


def check(readme_text: str, reference: dict, *, flat: bool = False, extra: dict[str, dict] | None = None) -> list[str]:
    """Problems found, as messages; an empty list means every number matches.
    `reference` is metrics.json, or (flat=True) the snapshot's {path: value}; `extra` maps a source name
    (see the module docstring) to its loaded JSON."""
    cells = parse_tables(readme_text)
    problems = []
    if not cells:
        problems.append("README.md has no metrics-table; the results table is missing")
    for path, line, cell, number in cells:
        try:
            want, rounded = _reference_for(path, reference, extra, flat)
        except KeyError:
            problems.append(f"README.md:{line}: `{path}` is not in the reference")
            continue
        if isinstance(want, bool) or not isinstance(want, (int, float)):
            problems.append(f"README.md:{line}: `{path}` is {want!r} in the reference, not a number")
        elif number is None:
            problems.append(f"README.md:{line}: `{path}`: {cell!r} is not a number (reference {want})")
        else:
            expected = round(float(want), decimals(cell)) if rounded else float(want)
            if number != expected:
                problems.append(f"README.md:{line}: `{path}`: README says {cell!r}, reference says {want}")
    return problems


def load_extra() -> dict[str, dict]:
    """The extra reference files that exist in this checkout."""
    return {name: json.loads(path.read_text()) for name, path in EXTRA_SOURCES.items() if path.exists()}


def snapshot_from(metrics: dict, readme_text: str, extra: dict[str, dict] | None = None) -> dict:
    out = {}
    for path, *_ in parse_tables(readme_text):
        out[path] = _reference_for(path, metrics, extra, False)[0]
    return out


def main(argv: list[str]) -> int:
    text = README.read_text()
    if "--write-snapshot" in argv:
        snap = snapshot_from(json.loads(METRICS.read_text()), text, load_extra())
        SNAPSHOT.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
        print(f"wrote {SNAPSHOT.relative_to(ROOT)} ({len(snap)} values)")
        return 0
    if METRICS.exists():
        problems = check(text, json.loads(METRICS.read_text()), extra=load_extra())
        source = "data/processed/metrics.json and " + ", ".join(sorted(load_extra())) + " (docs/oos, docs/chips)"
    else:
        problems = check(text, json.loads(SNAPSHOT.read_text()), flat=True)
        source = "docs/results_snapshot.json (metrics.json not present)"
    print("\n".join(problems) if problems else f"README results match {source}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
