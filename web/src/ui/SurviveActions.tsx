import { cut, restore, tradeState } from "../lib/surviveGame";
import { CUT_FRACTION } from "../lib/survive";
import { useSurvive } from "../state/survive";
import { useFrameIndex } from "../state/timeline";

/** Cut and Restore, above the playback controls, while a run is on. */
export function SurviveActions() {
  const phase = useSurvive((s) => s.phase);
  useSurvive((s) => s.sim); // a press changes the book
  const frame = useFrameIndex();
  if (phase !== "sailing") return null;
  const t = tradeState(frame);
  const why = t.blocked ?? undefined;
  return (
    <div className="panel survive-actions" role="group" aria-label="Cargo">
      <button className="act cut" onClick={cut} disabled={!t.canCut} title={why ?? (t.canCut ? "Throw 75% of the cargo overboard at the current price (key C)" : "The cargo is already cut")}>
        <span className="act-main">Cut</span>
        <span className="act-sub">throw {Math.round(CUT_FRACTION * 100)}% overboard</span>
      </button>
      <button
        className="act restore"
        onClick={restore}
        disabled={!t.canRestore}
        title={why ?? (t.canRestore ? "Hoist the cargo back aboard at the current price (key R)" : "Nothing to restore, or not enough margin to take it back yet")}
      >
        <span className="act-main">Restore</span>
        <span className="act-sub">cargo back aboard</span>
      </button>
    </div>
  );
}
