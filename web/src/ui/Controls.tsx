import { useMemo, useRef, type CSSProperties } from "react";
import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { SPEEDS, useTimeline } from "../state/timeline";
import { useApp } from "../state/app";
import { useSurvive } from "../state/survive";
import { fmtUtc } from "../lib/format";
import { captionLine, groupTicks, STORY_COLORS, storyEvents, type StoryEvent } from "./story";

export function Controls({ derived }: { derived: Derived }) {
  const t = useTimeline((s) => s.t);
  const playing = useTimeline((s) => s.playing);
  const speed = useTimeline((s) => s.speed);
  const { toggle, seek, setSpeed, play, pause } = useTimeline.getState();
  const wasPlaying = useRef(false);
  // Survive: a run cannot be scrubbed or replayed from the controls. Only sailing can be paused and resumed.
  const survive = useApp((st) => st.mode === "survive");
  const phase = useSurvive((st) => st.phase);
  const cantPlay = survive && phase !== "sailing";
  const frame = Math.min(derived.n - 1, Math.floor(t));
  const bundle = useApp((st) => st.bundle);
  const events = useMemo(
    () => (bundle ? storyEvents(bundle, { prepared: derived.ships.prepared.actions, unprepared: derived.ships.unprepared.actions }) : []),
    [bundle, derived],
  );

  return (
    <div className="panel controls">
      <button
        className="play"
        onClick={toggle}
        disabled={cantPlay}
        title={cantPlay ? (phase === "setup" ? "Press Sail to start" : "The run is over") : undefined}
        aria-label={playing ? "Pause" : "Play"}
      >
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
        <div className="scrub-track">
          <input
            type="range"
            min={0}
            max={derived.n - 1}
            step={0.01}
            value={t}
            style={{ "--p": `${derived.n > 1 ? (t / (derived.n - 1)) * 100 : 0}%` } as CSSProperties}
            aria-label="Replay position"
            disabled={survive}
            onPointerDown={() => {
              wasPlaying.current = useTimeline.getState().playing;
              pause();
            }}
            onPointerUp={() => {
              if (wasPlaying.current) play();
            }}
            onChange={(e) => seek(Number(e.target.value))}
          />
          {/* Survive: no ticks. The demo ships' events are not the player's, and the alarm's place would give the game away. */}
          {bundle && !survive && <Ticks bundle={bundle} events={events} n={derived.n} frame={frame} />}
        </div>
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

/** Ticks closer than this share of the replay are drawn as one tick (both events in its tooltip). */
const TICK_MERGE = 0.006;

/**
 * Every event of the replay as a small coloured tick on the scrubber, with a tooltip ("10:19 · Cut: The prepared ship
 * cuts 75% of its cargo"); clicking one jumps there. Ticks the playhead has passed are full strength.
 */
function Ticks({ bundle, events, n, frame }: { bundle: Bundle; events: StoryEvent[]; n: number; frame: number }) {
  const groups = useMemo(() => groupTicks(events, Math.max(1, Math.round((n - 1) * TICK_MERGE))), [events, n]);
  if (n < 2) return null;
  return (
    <div className="ticks">
      {groups.map((g) => {
        const at = g[0].i / (n - 1);
        return (
          <button
            key={`${g[0].i}-${g[0].kind}`}
            type="button"
            className={`tick ${g[0].i <= frame ? "passed" : ""} ${at < 0.35 ? "tip-l" : at > 0.65 ? "tip-r" : ""}`}
            style={{ left: `calc(var(--thumb) / 2 + (100% - var(--thumb)) * ${at})` }}
            onClick={() => useTimeline.getState().seek(g[0].i)}
            aria-label={`Jump to ${g.map((e) => `${e.name} at ${captionLine(bundle, e).split(" \u00b7 ")[0]}`).join(", ")}`}
          >
            {g.map((e, k) => (
              <span key={k} className="tick-seg" style={{ background: STORY_COLORS[e.kind] }} />
            ))}
            <span className="tick-tip" role="tooltip">
              {g.map((e, k) => (
                <span key={k} className="tick-tip-row">
                  <i style={{ background: STORY_COLORS[e.kind] }} />
                  {captionLine(bundle, e)}
                </span>
              ))}
            </span>
          </button>
        );
      })}
    </div>
  );
}
