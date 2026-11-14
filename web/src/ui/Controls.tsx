import { useRef } from "react";
import type { Derived } from "../lib/derive";
import { SPEEDS, useTimeline } from "../state/timeline";
import { fmtUtc } from "../lib/format";

export function Controls({ derived }: { derived: Derived }) {
  const t = useTimeline((s) => s.t);
  const playing = useTimeline((s) => s.playing);
  const speed = useTimeline((s) => s.speed);
  const { toggle, seek, setSpeed, play, pause } = useTimeline.getState();
  const wasPlaying = useRef(false);
  const frame = Math.min(derived.n - 1, Math.floor(t));

  return (
    <div className="panel controls">
      <button className="play" onClick={toggle} aria-label={playing ? "Pause" : "Play"}>
        {playing ? (
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <rect x="6" y="5" width="4" height="14" rx="1" />
            <rect x="14" y="5" width="4" height="14" rx="1" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M7 5v14l12-7z" />
          </svg>
        )}
      </button>
      <div className="scrub">
        <input
          type="range"
          min={0}
          max={derived.n - 1}
          step={0.01}
          value={t}
          aria-label="Replay position"
          onPointerDown={() => {
            wasPlaying.current = useTimeline.getState().playing;
            pause();
          }}
          onPointerUp={() => {
            if (wasPlaying.current) play();
          }}
          onChange={(e) => seek(Number(e.target.value))}
        />
        <div className="scrub-meta">
          <span>{fmtUtc(derived.times[frame], false)}</span>
          <span>
            min {frame + 1} / {derived.n}
          </span>
        </div>
      </div>
      <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Replay speed" title="Market minutes per 0.25 s">
        {SPEEDS.map((s) => (
          <option key={s} value={s}>
            {s}x
          </option>
        ))}
      </select>
    </div>
  );
}
