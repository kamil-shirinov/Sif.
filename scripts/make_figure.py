"""Draw the storm figure for the README from a replay bundle.

    ~/.venvs/stormscore/bin/python scripts/make_figure.py \
        [--bundle web/public/bundles/usdjpy-2026-07-30.json] [--out docs/img/usdjpy-2026-07-30.png]

Top: the pair's mid price. Bottom: equity of the ship that followed the alarm and the ship
that ignored it. Marked: the alarm, the cut fill, the margin call and the all-clear. Every
value and every time comes from the bundle; nothing is typed in here.
Needs matplotlib (a figure-only dependency, not in backend/requirements.txt).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Reference palette (dataviz skill): blue and orange pass the six checks on this surface.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
PREPARED, UNPREPARED = "#2a78d6", "#eb6834"
MARK = "#52514e"


def frame_time(b: dict, i: int) -> datetime:
    return datetime.fromtimestamp(b["t0"] + i * b["step_s"], tz=timezone.utc)


def first(events: list[dict], kind: str, **where) -> dict:
    for e in events:
        if e["type"] == kind and all(e.get(k) == v for k, v in where.items()):
            return e
    raise SystemExit(f"bundle has no {kind} event {where}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, default=ROOT / "web/public/bundles/usdjpy-2026-07-30.json")
    ap.add_argument("--out", type=Path, default=ROOT / "docs/img/usdjpy-2026-07-30.png")
    args = ap.parse_args()

    b = json.loads(args.bundle.read_text())
    s, ev, st = b["series"], b["events"], b["storm"]
    x = [frame_time(b, i) for i in range(b["n"])]
    onset_i, trough_i = st["onset_i"], st["trough_i"]

    alarm = first(ev, "alarm")["i"]
    cut = first(ev, "cut")["i"]
    margin = first(ev, "margin_call", ship="unprepared")["i"]
    clear = max(e["i"] for e in ev if e["type"] == "all_clear")  # the all-clear after the storm
    if not (alarm < cut < margin < clear):
        raise SystemExit("events are not in the expected order")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.6), dpi=110, sharex=True,
                                   gridspec_kw={"height_ratios": [1.05, 1], "hspace": 0.1, "top": 0.87},
                                   facecolor=SURFACE)
    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.axvspan(x[onset_i], x[trough_i], color="#efeeea", zorder=0, lw=0)  # onset to trough

    # Price
    ax1.plot(x, s["mid"], color=INK, linewidth=1.6)
    ax1.set_ylabel(f"{b['symbol']} mid")

    # Equity
    pe, ue = s["prepared_equity"], s["unprepared_equity"]
    ax2.plot(x, pe, color=PREPARED, linewidth=2)
    ax2.plot(x, ue, color=UNPREPARED, linewidth=2)
    ax2.set_ylabel("equity, synthetic book")
    ax2.yaxis.set_major_formatter(lambda v, _: f"${v / 1000:,.0f}k")
    ax2.plot([x[margin]], [ue[margin]], marker="o", markersize=8, color=UNPREPARED,
             markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
    ax2.set_ylim(min(min(pe), min(ue)) * 0.88, max(max(pe), max(ue)) * 1.04)
    ax2.set_xlim(x[0], x[-1] + (x[-1] - x[0]) * 0.17)  # room for the direct labels
    ax2.text(x[-1], pe[-1], f"  followed the alarm\n  ${pe[-1]:,.0f}", color=INK, va="center", fontsize=10)
    ax2.text(x[-1], ue[-1], f"  ignored it\n  ${ue[-1]:,.0f}", color=INK, va="center", fontsize=10)
    ax2.text(0.015, 0.06, "the two ships are identical until the cut", transform=ax2.transAxes, color=INK2, fontsize=9.5)
    for xy, c in ((pe[-1], PREPARED), (ue[-1], UNPREPARED)):
        ax2.plot([x[-1]], [xy], marker="o", markersize=7, color=c, markeredgecolor=SURFACE, markeredgewidth=1.5)

    # Marks: alarm and cut are one minute apart, so one label leans left and the other right
    marks = [
        (alarm, "alarm", "right"),
        (cut, "cut fills", "left"),
        (margin, "margin call", "left"),
        (clear, "all-clear", "left"),
    ]
    for i, label, ha in marks:
        for ax in (ax1, ax2):
            ax.axvline(x[i], color=MARK, linewidth=1.1, linestyle=(0, (4, 3)), zorder=1)
        gap = "  " if ha == "left" else "  "
        lines = f"{label}\n{x[i]:%H:%M}".split("\n")
        text = "\n".join((gap + t) if ha == "left" else (t + gap) for t in lines)
        ax1.text(x[i], 1.015, text, transform=ax1.get_xaxis_transform(), ha=ha, va="bottom",
                 color=INK, fontsize=9.5, linespacing=1.15)
    # The storm's facts, in the empty right-hand part of the price panel
    ax1.text(0.985, 0.93, f"storm {st['label']}\nonset {x[onset_i]:%H:%M}, trough {x[trough_i]:%H:%M}",
             transform=ax1.transAxes, ha="right", va="top", color=INK2, fontsize=10, linespacing=1.3)

    ax2.xaxis.set_major_locator(mdates.HourLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax2.set_xlabel(f"{x[0]:%-d %B %Y}, UTC (shaded: onset to trough)")
    fig.suptitle(b["title"], x=0.075, ha="left", y=0.99, fontsize=13, fontweight="bold", color=INK)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
