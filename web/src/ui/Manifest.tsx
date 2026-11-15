import { useState } from "react";
import type { Bundle, ShipKey, StressRow } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { useFrameIndex } from "../state/timeline";
import { fmtPct, fmtUsd } from "../lib/format";
import { ReportBody } from "./ReportPanel";
import { shortStress } from "./story";

type Tab = "cargo" | "stress" | "report";

/**
 * The right column's card. The two ships are the story and always show (equity, change, notional, margin buffer).
 * The book's cargo, the stress tests and the storm report sit behind tabs of the same card, all collapsed at first;
 * a second click on the open tab collapses it again.
 */
export function Manifest({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  const i = useFrameIndex();
  const [tab, setTab] = useState<Tab | null>(null);
  const ex = bundle.exposure;
  const report = bundle.report;
  const reportOk = report !== null && report.verified && report.unverified_numbers.length === 0;
  const tabs: { id: Tab; label: string; extra?: string; title: string }[] = [
    { id: "cargo", label: "Cargo", extra: `${ex.positions.length}`, title: "The book both ships carry: positions, leverage, net exposure" },
    { id: "stress", label: "Stress tests", extra: `${bundle.stress.length}`, title: "This book through earlier storms" },
  ];
  if (report) tabs.push({ id: "report", label: "Report", extra: reportOk ? "✓" : "!", title: reportOk ? "Storm report: numbers checked by code" : "Storm report: some numbers not verified" });
  const open = tab !== null && tabs.some((t) => t.id === tab) ? tab : null;

  return (
    <div className="panel manifest">
      <div className="panel-head">
        <span>Two ships, one book</span>
        {bundle.book_is_synthetic && <span className="badge synthetic">synthetic book</span>}
      </div>
      {(["prepared", "unprepared"] as ShipKey[]).map((k) => (
        <ShipRow key={k} k={k} i={i} derived={derived} />
      ))}
      <div className="book-line" title="Book notional, leverage and maintenance margin (exposure)">
        <span>{ex.positions.map((p) => p.instrument).join(" · ")}</span>
        <span className="num">
          {fmtUsd(derived.bookNotional, true)} · {ex.leverage.toFixed(1)}x
        </span>
      </div>
      <div className="card-tabs" role="tablist" aria-label="More about this book">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={open === t.id}
            aria-expanded={open === t.id}
            className={`card-tab ${open === t.id ? "on" : ""} ${t.id === "report" ? (reportOk ? "ok" : "warn") : ""}`}
            onClick={() => setTab(open === t.id ? null : t.id)}
            title={t.title}
          >
            {t.label}
            {t.extra && <span className="card-tab-extra">{t.extra}</span>}
          </button>
        ))}
      </div>
      {open === "cargo" && <Cargo bundle={bundle} derived={derived} />}
      {open === "stress" && <StressTests rows={bundle.stress} />}
      {open === "report" && report && (
        <div className="card-section report">
          <ReportBody report={report} />
        </div>
      )}
    </div>
  );
}

function Cargo({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  const ex = bundle.exposure;
  return (
    <div className="card-section">
      <table className="positions">
        <tbody>
          {ex.positions.map((p, k) => (
            <tr key={k}>
              <td>
                <div className="pos-inst">{p.instrument}</div>
                <div className="pos-side">{p.side}</div>
              </td>
              <td className="num">{fmtUsd(p.notional_usd, true)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="manifest-row">
        <span>Leverage</span>
        <span className="num">{ex.leverage.toFixed(1)}x</span>
      </div>
      <div className="manifest-row">
        <span>Net</span>
        <span className="num">
          {Object.entries(ex.net_usd_by_ccy)
            .map(([c, v]) => `${c} ${fmtUsd(v, true)}`)
            .join(" · ")}
        </span>
      </div>
      <div className="manifest-note">
        1 crate ≈ {fmtUsd(derived.crates[0]?.notionalUsd ?? 0, true)} notional · maintenance {(derived.maintenance * 100).toFixed(1)}%
      </div>
    </div>
  );
}

/** bundle.stress: this book through earlier storms (only storms whose trough came before the book's as-of frame). */
function StressTests({ rows }: { rows: StressRow[] }) {
  if (rows.length === 0) return <div className="card-section stress-empty">No earlier storms to test against yet</div>;
  return (
    <ul className="card-section stress-list">
      {rows.map((r, k) => {
        const s = shortStress(r);
        return (
          <li key={k} className="stress-line" title={s.full}>
            <span className="stress-what">
              {s.what}
              {s.move && <span className="tnum stress-move"> {s.move}</span>}
            </span>
            <span className="stress-res">
              <span className="stress-arrow" aria-hidden="true">
                →
              </span>{" "}
              <span className={`tnum ${r.pnl_usd >= 0 ? "up" : "down"}`}>{s.pnl}</span>
              <span className={s.marginCall ? "stress-mc" : "muted"}>, {s.marginCall ? "margin call" : "afloat"}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function ShipRow({ k, i, derived }: { k: ShipKey; i: number; derived: Derived }) {
  const s = derived.ships[k];
  const eq = s.equity[i];
  const chg = (eq / s.startEquity - 1) * 100;
  const buf = s.buffer[i];
  const closed = s.marginCallI !== null && i >= s.marginCallI;
  const tone = closed ? "dead" : buf < 0.2 ? "low" : buf < 0.45 ? "mid" : "ok";
  return (
    <div className={`ship-row ${k}`}>
      <div className="ship-row-head">
        <span className="ship-name">{s.label}</span>
        <span className="num">
          {fmtUsd(eq)} <span className={chg >= 0 ? "up" : "down"}>{fmtPct(chg)}</span>
        </span>
      </div>
      <div className="ship-row-sub">
        <span>
          Notional <span className="num">{fmtUsd(s.notional[i], true)}</span>
        </span>
        <span>
          {closed ? (
            "Margin call: closed"
          ) : (
            <>
              Margin buffer <span className="num">{(buf * 100).toFixed(1)}%</span>
            </>
          )}
        </span>
      </div>
      <div className="bar">
        <div className={`bar-fill ${tone}`} style={{ width: `${closed ? 0 : buf * 100}%` }} />
      </div>
    </div>
  );
}
