import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { useFrameIndex } from "../state/timeline";
import { useApp } from "../state/app";
import { fmtClock, fmtUtc, STATE_NAMES } from "../lib/format";
import { setMode } from "../lib/surviveGame";

export function Hud({ bundle, derived, onSound }: { bundle: Bundle; derived: Derived; onSound: () => void }) {
  const i = useFrameIndex();
  const soundOn = useApp((s) => s.soundOn && s.audioStarted);
  const lowQuality = useApp((s) => s.lowQuality);
  const setLowQuality = useApp((s) => s.setLowQuality);
  const webglOk = useApp((s) => s.webglOk);
  const mode = useApp((s) => s.mode);
  const tiger = useApp((s) => s.health?.tiger === true);
  const liveStatus = useApp((s) => s.liveStatus);
  const state = bundle.series.state[i] as 0 | 1 | 2;
  const risk = bundle.series.risk[i];
  const mid = bundle.series.mid[i];
  const prev = bundle.series.mid[Math.max(0, i - 1)];
  const fromStart = (mid / bundle.series.mid[0] - 1) * 10000;
  const onset = i >= bundle.storm.onset_i;
  const closed = derived.closed !== null && derived.closed[i] === 1;

  return (
    <div className="panel hud">
      <div className="hud-top">
        <div className="wordmark" aria-label="Sif">
          Sif<span aria-hidden="true">.</span>
        </div>
        <button
          className={`icon-btn ${soundOn ? "on" : ""}`}
          data-sound-toggle
          onClick={onSound}
          title={soundOn ? "Sound on (click to mute)" : "Sound off (click to turn on)"}
          aria-label={soundOn ? "Mute sound" : "Turn sound on"}
        >
          {soundOn ? <SpeakerOn /> : <SpeakerOff />}
        </button>
      </div>
      <div className="mode-switch" role="tablist" aria-label="Mode">
        <button role="tab" aria-selected={mode === "replay"} className={mode === "replay" ? "on" : ""} onClick={() => setMode("replay")} title="Watch the storm and the two demo ships">
          Replay
        </button>
        <button role="tab" aria-selected={mode === "survive"} className={mode === "survive" ? "on" : ""} onClick={() => setMode("survive")} title="Sail your own ship through the storm">
          Survive
        </button>
      </div>
      <div className="hud-symbol">
        <span className="symbol">{bundle.symbol}</span>
        <span className={`badge state-${state}`}>{STATE_NAMES[state]}</span>
        {closed && (
          <span className="badge closed" title="series.market_open is 0: prices hold their last trading value">
            Market closed
          </span>
        )}
        {bundle.source === "synthetic" && <span className="badge synthetic">synthetic data</span>}
        {bundle.source === "scenario" && (
          <span className="badge scenario whatif" title="A what-if scenario: the navigator resized a real storm. These prices are not market data and not real history.">
            <b>What if</b> {bundle.title.replace(/^\s*what[\s-]*if[:\s-]*/i, "")}
          </span>
        )}
        {tiger && (
          <span
            className={`badge live ${liveStatus}`}
            title={liveStatus === "failed" ? "Server is up, but its candles were not usable: the chart shows the bundle's own candles" : "Connected to the live server (GET /api/health)"}
          >
            Live · Tiger Data
          </span>
        )}
      </div>
      <div className="hud-price">
        <span className={mid >= prev ? "up" : "down"}>{mid.toFixed(derived.priceDecimals)}</span>
        <span className="hud-bp">{(fromStart >= 0 ? "+" : "") + fromStart.toFixed(0)} bp</span>
      </div>
      <div className="hud-time">
        {bundle.source === "scenario" ? `what-if clock ${fmtUtc(derived.times[i], false)}` : fmtUtc(derived.times[i])}
        {derived.exchangeTz && <span className="muted"> · {fmtClock(derived.times[i], derived.solarOffsetS[i])} New York</span>}
      </div>
      <div className="gauge" title="Storm risk score (series.risk)">
        <div className="gauge-label">
          <span>Storm risk</span>
          <span>{Math.round(risk * 100)}</span>
        </div>
        <div className="gauge-track">
          <div className="gauge-fill" style={{ width: `${risk * 100}%` }} />
        </div>
      </div>
      <div className="hud-storm">
        {bundle.storm.kind === "scheduled" ? `Scheduled event${bundle.storm.event ? ` · ${bundle.storm.event}` : ""}` : "Unscheduled storm"}
        {onset ? ` · ${bundle.storm.label}` : ""}
      </div>
      {webglOk && (
        <label className="quality">
          <input type="checkbox" checked={lowQuality} onChange={(e) => setLowQuality(e.target.checked)} /> Low quality
        </label>
      )}
    </div>
  );
}

function SpeakerOn() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 5 6 9H2v6h4l5 4V5z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7" />
      <path d="M19 5a10 10 0 0 1 0 14" />
    </svg>
  );
}

function SpeakerOff() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 5 6 9H2v6h4l5 4V5z" />
      <path d="m22 9-6 6" />
      <path d="m16 9 6 6" />
    </svg>
  );
}
