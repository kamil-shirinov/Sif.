import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { reopenFrame } from "../lib/derive";
import { fmtClock, fmtPct, fmtUsd } from "../lib/format";
import { chooseLeverage, sail, tradeState, tryAgain } from "../lib/surviveGame";
import { MIN_LEVERAGE, legFor, maxLeverageFor } from "../lib/survive";
import { useApp } from "../state/app";
import { useSurvive } from "../state/survive";
import { useFrameIndex } from "../state/timeline";
import { useState } from "react";
import { Tutorial } from "./survive/Tutorial";
import { tutorialGate } from "./survive/tutorialCards";
import { StormList, useCurrentRating } from "./survive/StormList";
import { DIFFICULTY_NAMES } from "./survive/difficulty";
import { Coach } from "./survive/Coach";
import "../survive.css";

const priceStr = (x: number, decimals: number) => (Number.isFinite(x) ? x.toFixed(decimals) : "n/a");

/** Survive mode's panel: pick a storm and a leverage, then sail; while sailing, the ship's books. */
export function SurvivePanel({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  const phase = useSurvive((s) => s.phase);
  const landing = useApp((s) => s.landing);
  // First run: the three tutorial cards, once (tutorial.ts guards the storage). "How to play" opens them again.
  const [tutorial, setTutorial] = useState(() => tutorialGate().shouldShow());
  const closeTutorial = () => {
    tutorialGate().markSeen();
    setTutorial(false);
  };
  return (
    <div className="panel survive">
      <div className="panel-head">
        <span>Survive the storm</span>
        <span className="badge synthetic">synthetic book</span>
      </div>
      {phase === "setup" ? <Setup bundle={bundle} derived={derived} onHowTo={() => setTutorial(true)} /> : <Sailing bundle={bundle} derived={derived} />}
      {tutorial && phase === "setup" && !landing && <Tutorial bundle={bundle} onClose={closeTutorial} />}
    </div>
  );
}

function Setup({ bundle, derived, onHowTo }: { bundle: Bundle; derived: Derived; onHowTo: () => void }) {
  const leverage = useSurvive((s) => s.leverage);
  const line = useSurvive((s) => s.line);
  const sim = useSurvive((s) => s.sim);
  const max = maxLeverageFor(bundle);
  const leg = legFor(bundle);
  const rating = useCurrentRating(bundle);
  if (!line || !sim) return null;
  const crateCount = Math.min(30, line.crates);
  const decimals = derived.priceDecimals;
  const zero = Math.abs(line.zeroMovePct);
  const call = Math.abs(line.movePct);
  const callAt = zero > 0 ? Math.min(100, (call / zero) * 100) : 0;
  return (
    <>
      <p className="survive-intro">
        Start with <b>{fmtUsd(sim.startEquity, true)}</b>. More cargo means bigger gains, and sinking faster.{" "}
        <button className="survive-howto" onClick={onHowTo}>
          How to play
        </button>
      </p>
      <StormList bundle={bundle} />
      <div className="survive-storm">
        <span className="muted">The sea ahead</span> {rating && <span className={`diff-chip lvl-${rating.level}`}>{DIFFICULTY_NAMES[rating.level]}</span>} <b>{bundle.storm.label}</b>
        {bundle.storm.kind === "scheduled" && bundle.storm.event ? <span className="muted"> · around {bundle.storm.event}</span> : null}
      </div>
      <label className="survive-field">
        <span className="survive-label">
          Leverage <b className="survive-lev">{leverage}x</b>
        </span>
        <input
          type="range"
          min={MIN_LEVERAGE}
          max={max}
          step={1}
          value={leverage}
          onChange={(e) => chooseLeverage(Number(e.target.value))}
          aria-label="Leverage"
          aria-valuetext={`${leverage}x: ${line.crates} crates, margin call at ${priceStr(line.price, decimals)}`}
        />
        <span className="survive-ticks">
          <span>{MIN_LEVERAGE}x</span>
          <span>{max}x</span>
        </span>
      </label>
      {max < 30 && (
        <p className="survive-note">Equity books top out at {max}x: with {(derived.maintenance * 100).toFixed(0)}% maintenance, any bigger bet is below the margin line on the very first minute.</p>
      )}
      <div className="survive-cargo">
        <div className="crate-strip" aria-label={`${line.crates} crates of cargo`}>
          {Array.from({ length: crateCount }, (_, k) => (
            <span key={k} className="crate" style={{ background: CRATE_COLORS[k % CRATE_COLORS.length] }} />
          ))}
        </div>
        <div className="survive-cargo-text">
          <b>{line.crates}</b> {line.crates === 1 ? "crate" : "crates"} · {fmtUsd(line.notional, true)} cargo · {leg.position}
          {line.crates > 24 && <span className="muted"> (the ship draws 24 bigger crates)</span>}
        </div>
      </div>
      <div className="survive-line">
        <span className="line-dot" />
        <span>
          Margin call at <b className="num">{priceStr(line.price, decimals)}</b> <span className="muted">({fmtPct(line.movePct, 1)} from entry)</span>
        </span>
      </div>
      <div className="line-meter" title="How far the price may move against you before the broker closes you out">
        <div className="line-track">
          <span className="line-mark call" style={{ left: `${callAt}%` }} />
        </div>
        <div className="line-labels">
          <span>entry {priceStr(bundle.series.mid[0], decimals)}</span>
          <span>stake gone at {zero.toFixed(1)}%</span>
        </div>
      </div>
      <p className="survive-note">Red dashed line on the chart · maintenance {(derived.maintenance * 100).toFixed(1)}% of the cargo</p>
      <button className="sail-btn" onClick={sail}>
        Sail
      </button>
    </>
  );
}

const CRATE_COLORS = ["#c47f36", "#3f7fc4", "#5aa168", "#c14b4b", "#8b6cc4", "#c4b13f"];

function Sailing({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  const i = useFrameIndex();
  const phase = useSurvive((s) => s.phase);
  const sim = useSurvive((s) => s.sim);
  const result = useSurvive((s) => s.result);
  if (!sim || !derived.player) return null;
  const ship = derived.player;
  const f = Math.min(derived.n - 1, i);
  const equity = sim.equity[f];
  const chg = (equity / sim.startEquity - 1) * 100;
  const sunk = sim.marginCallI !== null && f >= sim.marginCallI;
  const buf = ship.buffer[f];
  const tone = sunk ? "dead" : buf < 0.2 ? "low" : buf < 0.45 ? "mid" : "ok";
  const held = sim.held[f];
  const liq = sim.liq[f];
  const price = bundle.series.mid[f];
  const away = Number.isFinite(liq) ? (liq / price - 1) * 100 : null;
  const t = tradeState(f);
  const closed = derived.closed !== null && derived.closed[f] === 1;
  const reopen = closed ? reopenFrame(derived, f) : null;
  return (
    <>
      <div className="survive-equity">
        <span className="num survive-equity-big">{fmtUsd(Math.max(0, equity))}</span>
        <span className={`num ${chg >= 0 ? "up" : "down"}`}>{fmtPct(chg)}</span>
      </div>
      <Coach bundle={bundle} sim={sim} frame={f} />
      <div className="manifest-row">
        <span>Leverage</span>
        <span className="num">{sim.leverage}x</span>
      </div>
      <div className="manifest-row">
        <span>Cargo</span>
        <span className="num">
          {sunk ? "lost" : held === 1 ? "whole" : held === 0 ? "none" : `${Math.round(held * 100)}% aboard`} · {fmtUsd(sim.notional[f], true)}
        </span>
      </div>
      <div className="ship-row-sub">
        <span>{sunk ? "Margin call: closed" : `Margin buffer ${(buf * 100).toFixed(1)}%`}</span>
        <span className="muted">0% = sunk</span>
      </div>
      <div className="bar">
        <div className={`bar-fill ${tone}`} style={{ width: `${sunk ? 0 : buf * 100}%` }} />
      </div>
      {!sunk && Number.isFinite(liq) && (
        <div className="survive-line">
          <span className="line-dot" />
          <span>
            Margin call at <b className="num">{priceStr(liq, derived.priceDecimals)}</b> <span className="muted">({away !== null ? fmtPct(away, 1) : ""} from here)</span>
          </span>
        </div>
      )}
      {closed && (
        <p className="survive-note">
          Market closed: prices hold{reopen !== null ? ` until ${fmtClock(derived.times[reopen])} UTC` : ""}. You cannot trade.
        </p>
      )}
      {phase === "sailing" && !closed && !sunk && <p className="survive-note">Cut throws 75% of the cargo overboard at the current price. Keys: C cuts, R restores.</p>}
      {t.blocked && !closed && <p className="survive-note">{t.blocked}</p>}
      {phase === "over" && result && (
        <button className="sail-btn" onClick={tryAgain}>
          Try again
        </button>
      )}
    </>
  );
}
