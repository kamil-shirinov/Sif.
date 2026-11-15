"""Read the numbers in the results tables of README.md and docs/results.md and check them against metrics.json.

Every file in DOCS is checked the same way; a table may sit in any of them.

A results table in the README is preceded by a marker line

    <!-- metrics-table: methods.{col}. -->

A marker may name another reference file in square brackets, and the table is then checked against it
(`oos1` = docs/oos/results.json, `oos2` = docs/oos/results-2.json, `chips` = docs/chips/results.json,
`stats` = docs/stats/results.json):

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

A table whose cells mix sources, with plain-words headers, is preceded by a multi-line marker that names
each value cell's full path, one line per body row, cells separated by `|`, `-` for a cell that is not a number
to check; the first column (the row's label) is never checked:

    <!-- metrics-cells
    evidence::datasets.0.headline.storms | evidence::datasets.0.headline.caught | -
    stats::groups.sgx_august.point.storms | stats::groups.sgx_august.point.caught | -
    -->

(`evidence` = web/public/evidence.json, the Explorer's data, built from the published result files.)

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
RESULTS = ROOT / "docs" / "results.md"
DOCS = [README, RESULTS]
METRICS = ROOT / "data" / "processed" / "metrics.json"
SNAPSHOT = ROOT / "docs" / "results_snapshot.json"

MARKER = re.compile(r"^<!--\s*metrics-table(?:\[(\w+)\])?:\s*(.*?)\s*-->\s*$")
CELLS_MARKER = re.compile(r"^<!--\s*metrics-cells\s*$")
EXTRA_SOURCES = {
    "oos1": ROOT / "docs" / "oos" / "results.json",
    "oos2": ROOT / "docs" / "oos" / "results-2.json",
    "chips": ROOT / "docs" / "chips" / "results.json",
    "stats": ROOT / "docs" / "stats" / "results.json",
    "evidence": ROOT / "web" / "public" / "evidence.json",
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
        if CELLS_MARKER.match(lines[i]):
            i = _parse_cells_table(lines, i + 1, out)
            continue
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


def _parse_cells_table(lines: list[str], i: int, out: list) -> int:
    """A `metrics-cells` marker starting at line i (after `<!-- metrics-cells`): read its path rows, then the table."""
    rows = []
    while i < len(lines) and lines[i].strip() != "-->":
        if lines[i].strip():
            rows.append([c.strip() for c in lines[i].split("|")])
        i += 1
    if i >= len(lines):
        raise ValueError("a metrics-cells marker is not closed with -->")
    i += 1
    if i >= len(lines) or not lines[i].lstrip().startswith("|"):
        raise ValueError(f"line {i}: a metrics-cells marker must be followed by a table")
    width = len(_cells(lines[i])) - 1
    i += 2  # header and the |---| line
    k = 0
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        if k >= len(rows):
            raise ValueError(f"line {i + 1}: the table has more rows than its metrics-cells marker")
        cells = _cells(lines[i])[1:]
        if len(rows[k]) != width or len(cells) != width:
            raise ValueError(f"line {i + 1}: the marker names {len(rows[k])} cells, the table has {width} value columns")
        for path, cell in zip(rows[k], cells):
            if path != "-":
                out.append((path, i + 1, cell, to_number(cell)))
        i += 1
        k += 1
    if k != len(rows):
        raise ValueError(f"line {i}: the metrics-cells marker has {len(rows)} rows, the table {k}")
    return i


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
    """Walk a dotted path; a number indexes a list ("ci95.0"); a trailing "@pct" multiplies by 100
    (the stats file keeps shares as fractions, the README shows percentages)."""
    scale = 1.0
    if path.endswith("@pct"):
        path, scale = path[: -len("@pct")], 100.0
    node = metrics
    for part in path.split("."):
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise KeyError(path)
    if scale != 1.0:
        if isinstance(node, bool) or not isinstance(node, (int, float)):
            raise KeyError(path)
        node = node * scale
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


def check(readme_text: str, reference: dict, *, flat: bool = False, extra: dict[str, dict] | None = None,
          name: str = "README.md", require_table: bool = True) -> list[str]:
    """Problems found, as messages; an empty list means every number matches.
    `reference` is metrics.json, or (flat=True) the snapshot's {path: value}; `extra` maps a source name
    (see the module docstring) to its loaded JSON."""
    cells = parse_tables(readme_text)
    problems = []
    if not cells and require_table:
        problems.append(f"{name} has no metrics-table; the results table is missing")
    for path, line, cell, number in cells:
        try:
            want, rounded = _reference_for(path, reference, extra, flat)
        except KeyError:
            problems.append(f"{name}:{line}: `{path}` is not in the reference")
            continue
        if isinstance(want, bool) or not isinstance(want, (int, float)):
            problems.append(f"{name}:{line}: `{path}` is {want!r} in the reference, not a number")
        elif number is None:
            problems.append(f"{name}:{line}: `{path}`: {cell!r} is not a number (reference {want})")
        else:
            expected = round(float(want), decimals(cell)) if rounded else float(want)
            if number != expected:
                problems.append(f"{name}:{line}: `{path}`: README says {cell!r}, reference says {want}")
    return problems


def docs() -> list[tuple[str, str]]:
    """(name, text) of every checked file that exists in this checkout."""
    return [(str(p.relative_to(ROOT)), p.read_text()) for p in DOCS if p.exists()]


def check_all(reference: dict, *, flat: bool = False, extra: dict[str, dict] | None = None) -> list[str]:
    """check() over every file in DOCS; README.md must have a table, the others may hold none."""
    problems = []
    for name, text in docs():
        problems += check(text, reference, flat=flat, extra=extra, name=name, require_table=name == "README.md")
    return problems


def all_cells() -> list[tuple[str, int, str, float | None]]:
    return [c for _, text in docs() for c in parse_tables(text)]


def load_extra() -> dict[str, dict]:
    """The extra reference files that exist in this checkout."""
    return {name: json.loads(path.read_text()) for name, path in EXTRA_SOURCES.items() if path.exists()}


def snapshot_from(metrics: dict, readme_text: str | None = None, extra: dict[str, dict] | None = None) -> dict:
    """{path: value} for every cell of the given text, or (None) of every checked file."""
    out = {}
    cells = parse_tables(readme_text) if readme_text is not None else all_cells()
    for path, *_ in cells:
        out[path] = _reference_for(path, metrics, extra, False)[0]
    return out


def main(argv: list[str]) -> int:
    if "--write-snapshot" in argv:
        snap = snapshot_from(json.loads(METRICS.read_text()), None, load_extra())
        SNAPSHOT.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
        print(f"wrote {SNAPSHOT.relative_to(ROOT)} ({len(snap)} values)")
        return 0
    names = ", ".join(name for name, _ in docs())
    if METRICS.exists():
        problems = check_all(json.loads(METRICS.read_text()), extra=load_extra())
        source = "data/processed/metrics.json and " + ", ".join(sorted(load_extra()))
    else:
        problems = check_all(json.loads(SNAPSHOT.read_text()), flat=True)
        source = "docs/results_snapshot.json (metrics.json not present)"
    print("\n".join(problems) if problems else f"{names}: {len(all_cells())} numbers match {source}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
