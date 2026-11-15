import { useState } from "react";
import type { Bundle } from "../types/bundle";
import { fmtClock, fmtPct, fmtUsd } from "../lib/format";
import { setMode, tryAgain } from "../lib/surviveGame";
import { explain } from "../lib/survive";
import { useSurvive } from "../state/survive";
import { DIFFICULTY_NAMES } from "./survive/difficulty";
import { alarmFollower, lessonFor, shareLine, shareUrl, whatHappened } from "./survive/endcard";
import { useCurrentRating } from "./survive/StormList";

const when = (b: Bundle, i: number) => `${fmtClock(b.t0 + i * b.step_s)} UTC`;

/** The end of a run: what happened, what the alarm-follower did, one lesson, a line to share, the storm's best scores. */
export function SurviveCard({ bundle }: { bundle: Bundle }) {
  const phase = useSurvive((s) => s.phase);
  const result = useSurvive((s) => s.result);
  const rank = useSurvive((s) => s.rank);
  const best = useSurvive((s) => s.best);
  const rating = useCurrentRating(bundle);
  if (phase !== "over" || !result) return null;
  const mine = best.filter((e) => e.storm_id === bundle.storm_id).sort((a, b) => b.score - a.score);
  const url = result.scenario || typeof window === "undefined" ? "" : shareUrl(window.location.href, bundle.storm_id);
  const share = shareLine(bundle, result, rating ? DIFFICULTY_NAMES[rating.level] : null, url || undefined);
  // "New best" only when the run beats an earlier score on this storm, not on a first run.
  const newBest = !result.scenario && rank === 1 && mine.length > 1;
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
        <div className="card-title">
          {result.sunk ? "Sunk!" : "Land ho!"}
          {newBest && <span className="new-best">New best on this storm</span>}
        </div>
        <div className="card-score">
          <span className="num big">{fmtUsd(result.score)}</span>
          <span className={`num ${result.changePct >= 0 ? "up" : "down"}`}>{fmtPct(result.changePct)}</span>
          <span className="muted">
            {result.leverage}x on {bundle.symbol}
            {result.scenario ? " · what-if" : ""}
          </span>
          {rating && <span className={`diff-chip lvl-${rating.level}`}>{DIFFICULTY_NAMES[rating.level]}</span>}
        </div>

        <div className="card-section">
          <div className="card-h">What happened</div>
          <p>{whatHappened(bundle, result)}</p>
        </div>
        <div className="card-section">
          <div className="card-h">The ship that followed the alarm</div>
          <p>{alarmFollower(bundle, result)}</p>
          <table className="card-compare">
            <tbody>
              <tr className="you">
                <td>Your run</td>
                <td className="num">{fmtUsd(result.score)}</td>
                <td className="muted">
                  {result.sunk && result.marginCallI !== null
                    ? `sunk at ${when(bundle, result.marginCallI)}`
                    : result.cuts > 0
                      ? `${result.cuts} cut${result.cuts > 1 ? "s" : ""}`
                      : "held the whole way"}
                </td>
              </tr>
              {result.followed && (
                <tr>
                  <td>Followed the alarm</td>
                  <td className="num">{fmtUsd(Math.max(0, result.followed.equity))}</td>
                  <td className="muted">
                    {result.followed.sunk && result.followed.marginCallI !== null
                      ? `sunk at ${when(bundle, result.followed.marginCallI)}`
                      : result.followed.cutI !== null
                        ? `cut filled ${when(bundle, result.followed.cutI)}`
                        : "afloat"}
                  </td>
                </tr>
              )}
              <tr>
                <td>Held everything</td>
                <td className="num">{fmtUsd(Math.max(0, result.held.equity))}</td>
                <td className="muted">{result.held.sunk && result.held.marginCallI !== null ? `sunk at ${when(bundle, result.held.marginCallI)}` : "afloat"}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="card-lesson">
          <span className="card-h">Lesson</span>
          <p>{lessonFor(bundle, result)}</p>
        </div>
        <ShareLine text={share} />
        <details className="card-more">
          <summary>More detail</summary>
          <div className="card-lines">
            {explain(bundle, result).map((l, k) => (
              <p key={k}>{l}</p>
            ))}
          </div>
        </details>
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

/** The share line with a Copy button. The clipboard can be missing or refused: the text stays selectable either way. */
function ShareLine({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = async () => {
    try {
      if (!navigator.clipboard) throw new Error("no clipboard");
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
  };
  return (
    <div className="card-share">
      <div className="card-h">Share your score</div>
      <div className="share-row">
        <input className="share-text" readOnly value={text} aria-label="Score line to share" onFocus={(e) => e.currentTarget.select()} />
        <button className="ghost-btn share-copy" onClick={() => void copy()}>
          {state === "copied" ? "Copied" : "Copy"}
        </button>
      </div>
      {state === "failed" && <p className="muted share-note">Copying is blocked here: select the line and copy it yourself.</p>}
    </div>
  );
}
