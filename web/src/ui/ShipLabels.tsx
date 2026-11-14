import type { Bundle, ShipKey } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { useFrameIndex } from "../state/timeline";
import { fmtPct, fmtUsd } from "../lib/format";
import { labelEls } from "../scene/labels";

/** Labels above the two ships (text from ships.*.label); the 3D scene positions them each frame. */
export function ShipLabels({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  const i = useFrameIndex();
  return (
    <>
      {(["prepared", "unprepared"] as ShipKey[]).map((k) => {
        const ship = derived.ships[k];
        const eq = ship.equity[i];
        const chg = (eq / ship.startEquity - 1) * 100;
        const sunk = ship.marginCallI !== null && i >= ship.marginCallI;
        const cut = ship.cutI !== null && i >= ship.cutI && ship.cutFraction > 0;
        const mc = bundle.events.find((e) => e.type === "margin_call" && e.ship === k);
        return (
          <div
            key={k}
            className={`ship-label ${k} ${sunk ? "sunk" : ""}`}
            ref={(el) => {
              if (el) labelEls.set(`ship-${k}`, el);
              else labelEls.delete(`ship-${k}`);
            }}
          >
            <div className="ship-label-name">{ship.label}</div>
            <div className="ship-label-eq">
              {fmtUsd(eq, true)} <span className={chg >= 0 ? "up" : "down"}>{fmtPct(chg)}</span>
            </div>
            {sunk && <div className="ship-label-status">{mc ? mc.text : "Margin call"}</div>}
            {!sunk && cut && <div className="ship-label-status">Cut {Math.round(ship.cutFraction * 100)}% of cargo</div>}
          </div>
        );
      })}
    </>
  );
}
