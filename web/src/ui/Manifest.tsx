import type { Bundle, ShipKey } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { MAINTENANCE_RATE } from "../lib/derive";
import { useFrameIndex } from "../state/timeline";
import { fmtPct, fmtUsd } from "../lib/format";

export function Manifest({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  const i = useFrameIndex();
  const ex = bundle.exposure;
  return (
    <div className="panel manifest">
      <div className="panel-head">
        <span>Cargo manifest</span>
        {bundle.book_is_synthetic && <span className="badge synthetic">synthetic book</span>}
      </div>
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
        1 crate ≈ {fmtUsd(derived.crates[0]?.notionalUsd ?? 0, true)} notional · maintenance {(MAINTENANCE_RATE * 100).toFixed(1)}%
      </div>
      {(["prepared", "unprepared"] as ShipKey[]).map((k) => (
        <ShipRow key={k} k={k} i={i} derived={derived} />
      ))}
    </div>
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
        <span>Notional {fmtUsd(s.notional[i], true)}</span>
        <span>{closed ? "Margin call: closed" : `Margin buffer ${(buf * 100).toFixed(1)}%`}</span>
      </div>
      <div className="bar">
        <div className={`bar-fill ${tone}`} style={{ width: `${closed ? 0 : buf * 100}%` }} />
      </div>
    </div>
  );
}
