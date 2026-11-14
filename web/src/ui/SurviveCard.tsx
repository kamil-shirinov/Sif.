import type { Bundle } from "../types/bundle";
import { fmtClock, fmtPct, fmtUsd } from "../lib/format";
import { setMode, tryAgain } from "../lib/surviveGame";
import { explain } from "../lib/survive";
import { useSurvive } from "../state/survive";

const when = (b: Bundle, i: number) => `${fmtClock(b.t0 + i * b.step_s)} UTC`;

/** The end of a run: what happened in plain words, what-ifs, the storm's best scores, Try again. */
export function SurviveCard({ bundle }: { bundle: Bundle }) {
  const phase = useSurvive((s) => s.phase);
  const result = useSurvive((s) => s.result);
  const rank = useSurvive((s) => s.rank);
  const best = useSurvive((s) => s.best);
  if (phase !== "over" || !result) return null;
  const mine = best.filter((e) => e.storm_id === bundle.storm_id).sort((a, b) => b.score - a.score);
  const lines = explain(bundle, result);
  return (
    <div className="survive-card-wrap">
      <div className={`panel survive-card ${result.sunk ? "sunk" : "landed"}`} role="dialog" aria-label="Run summary">
        {!result.sunk && (
          <div className="confetti" aria-hidden="true">
            {Array.from({ length: 16 }, (_, k) => (
              <span key={k} style={{ left: `${(k * 53) % 100}%`, animationDelay: `${(k % 8) * 0.12}s`, background: ["#f5a623", "#5ecf9a", "#7cc4ff", "#ef7a7a", "#c4b13f"][k % 5] }} />
            ))}
          </div>
        )}
        <div className="card-title">{result.sunk ? "Sunk!" : "Land ho!"}</div>
        <div className="card-score">
          <span className="num big">{fmtUsd(result.score)}</span>
          <span className={`num ${result.changePct >= 0 ? "up" : "down"}`}>{fmtPct(result.changePct)}</span>
          <span className="muted">
            {result.leverage}x on {bundle.symbol}
            {result.scenario ? " · what-if" : ""}
          </span>
        </div>
        <div className="card-lines">
          {lines.map((l, k) => (
            <p key={k}>{l}</p>
          ))}
        </div>
        <table className="card-compare">
          <tbody>
            <tr className="you">
              <td>Your run</td>
              <td className="num">{fmtUsd(result.score)}</td>
              <td className="muted">{result.sunk && result.marginCallI !== null ? `sunk at ${when(bundle, result.marginCallI)}` : result.cuts > 0 ? `${result.cuts} cut${result.cuts > 1 ? "s" : ""}` : "held the whole way"}</td>
            </tr>
            <tr>
              <td>Held everything</td>
              <td className="num">{fmtUsd(Math.max(0, result.held.equity))}</td>
              <td className="muted">{result.held.sunk && result.held.marginCallI !== null ? `sunk at ${when(bundle, result.held.marginCallI)}` : "afloat"}</td>
            </tr>
            {result.followed && (
              <tr>
                <td>Cut at the alarm</td>
                <td className="num">{fmtUsd(Math.max(0, result.followed.equity))}</td>
                <td className="muted">{result.followed.sunk && result.followed.marginCallI !== null ? `sunk at ${when(bundle, result.followed.marginCallI)}` : `alarm ${when(bundle, result.followed.cutI)}`}</td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="card-best">
          <div className="panel-head">
            <span>Best scores · this storm</span>
            <span className="muted">kept on this device</span>
          </div>
          {result.scenario ? (
            <p className="muted">What-if runs are practice: they are not saved.</p>
          ) : mine.length === 0 ? (
            <p className="muted">No scores on this device yet.</p>
          ) : (
            <table className="best-table">
              <tbody>
                {mine.map((e, k) => (
                  <tr key={`${e.at}-${k}`} className={rank === k + 1 ? "new" : ""}>
                    <td className="muted">{k + 1}</td>
                    <td className="num">{fmtUsd(e.score)}</td>
                    <td>{e.leverage}x</td>
                    <td className="muted">{e.sunk ? "sunk" : "afloat"}</td>
                    <td className="muted">{rank === k + 1 ? "this run" : e.at.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="card-actions">
          <button className="sail-btn" onClick={tryAgain} autoFocus>
            Try again
          </button>
          <button className="ghost-btn" onClick={() => setMode("replay")}>
            Watch the replay
          </button>
        </div>
      </div>
    </div>
  );
}
