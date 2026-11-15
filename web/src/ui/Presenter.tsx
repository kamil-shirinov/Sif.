import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { useApp } from "../state/app";
import { useFrameIndex, useTimeline } from "../state/timeline";
import { fmtPct, fmtUsd } from "../lib/format";
import { showLanding } from "../landing/actions";
import { crossed, endFacts, frameClock, STORY_COLORS, type StoryEvent, type StoryKind } from "./story";

/**
 * What the presenter sees on top of the replay, mounted from Controls (always on screen with the overlay) and portalled
 * to <body>, so it can sit anywhere without App.tsx changing: the captions at the bottom centre and, at the replay's
 * last frame, the end card.
 */
export function PresenterLayer({ bundle, events }: { bundle: Bundle; derived: Derived; events: StoryEvent[] }) {
  const replay = useApp((s) => s.mode === "replay");
  if (typeof document === "undefined") return null;
  return createPortal(
    <>
      {replay && <Captions bundle={bundle} events={events} />}
      {replay && <EndCard bundle={bundle} />}
    </>,
    document.body,
  );
}

/**
 * At the replay's last frame: both ships' final equity, the difference and any margin call with its time, all read
 * from the bundle (ui/story.ts: endFacts). Gone again as soon as the playhead leaves the last frame.
 */
function EndCard({ bundle }: { bundle: Bundle }) {
  const i = useFrameIndex();
  if (bundle.n < 2 || i < bundle.n - 1) return null;
  const f = endFacts(bundle);
  const replay = () => {
    const tl = useTimeline.getState();
    tl.seek(0);
    tl.play();
  };
  return (
    <div className="end-card" role="dialog" aria-label="End of the replay">
      <div className="end-title">End of the replay</div>
      <div className="end-ships">
        {f.ships.map((s) => (
          <div key={s.key} className={`end-ship ${s.key}`}>
            <div className="end-name">{s.label}</div>
            <div className="end-eq">
              <span className="num">{fmtUsd(s.final)}</span> <span className={`num ${s.changePct >= 0 ? "up" : "down"}`}>{fmtPct(s.changePct)}</span>
            </div>
            <div className={s.marginCall ? "end-mc" : "end-afloat"}>{s.marginCall ? `Margin call ${s.marginCall.time}` : "Afloat"}</div>
          </div>
        ))}
      </div>
      <div className="end-diff">
        <span>{f.lead}</span>
        {f.amount && <span className="num">{f.amount}</span>}
      </div>
      <div className="end-actions">
        <button className="sail-btn" onClick={replay}>
          Replay
        </button>
        <button className="ghost-btn" onClick={showLanding}>
          Back to landing <kbd>L</kbd>
        </button>
      </div>
    </div>
  );
}

/** A caption shows at least this long before the next one in the queue replaces it. */
const MIN_MS = 2200;
/** A caption with nothing after it stays this long, then fades. */
const HOLD_MS = 4200;
const FADE_MS = 450;
/** Captions waiting behind the one on screen; older ones are dropped at high speed. */
const MAX_QUEUE = 2;

interface Shown {
  id: number;
  kind: StoryKind;
  time: string;
  text: string;
  leaving: boolean;
}

/**
 * One plain-English line per event as the playhead passes it ("10:19 · The prepared ship cuts 75% of its cargo"),
 * fading after a few seconds. Built from the bundle's events only (ui/story.ts). A jump onto an event's frame
 * (a tick click) shows that event's caption; any other jump shows nothing.
 */
function Captions({ bundle, events }: { bundle: Bundle; events: StoryEvent[] }) {
  const [shown, setShown] = useState<Shown | null>(null);
  const queue = useRef<StoryEvent[]>([]);
  const phase = useRef<"idle" | "min" | "hold">("idle");
  const timer = useRef(0);
  const seq = useRef(0);

  useEffect(() => {
    queue.current = [];
    phase.current = "idle";
    setShown(null);

    const showNext = () => {
      window.clearTimeout(timer.current);
      const e = queue.current.shift();
      if (!e) {
        phase.current = "idle";
        setShown((s) => (s ? { ...s, leaving: true } : s));
        timer.current = window.setTimeout(() => setShown(null), FADE_MS);
        return;
      }
      phase.current = "min";
      setShown({ id: ++seq.current, kind: e.kind, time: frameClock(bundle, e.i), text: e.text, leaving: false });
      timer.current = window.setTimeout(() => {
        if (queue.current.length > 0) return showNext();
        phase.current = "hold";
        timer.current = window.setTimeout(showNext, HOLD_MS - MIN_MS);
      }, MIN_MS);
    };
    const enqueue = (es: StoryEvent[]) => {
      if (es.length === 0) return;
      queue.current.push(...es);
      if (queue.current.length > MAX_QUEUE) queue.current.splice(0, queue.current.length - MAX_QUEUE);
      if (phase.current !== "min") showNext();
    };

    const st = useTimeline.getState();
    let prevFrame = st.t === 0 ? -1 : Math.floor(st.t);
    let prevEpoch = st.seekEpoch;
    const unsub = useTimeline.subscribe((s) => {
      const frame = Math.min(s.n - 1, Math.floor(s.t));
      if (s.seekEpoch !== prevEpoch) {
        prevEpoch = s.seekEpoch;
        prevFrame = s.t === 0 ? -1 : frame;
        enqueue(events.filter((e) => e.i === frame && s.t > 0));
        return;
      }
      if (frame > prevFrame) {
        enqueue(crossed(events, prevFrame, frame));
        prevFrame = frame;
      }
    });
    return () => {
      unsub();
      window.clearTimeout(timer.current);
    };
  }, [bundle, events]);

  if (!shown) return null;
  return (
    <div className="caption-bar" aria-live="polite">
      <div key={shown.id} className={`caption ${shown.leaving ? "leaving" : ""}`} style={{ borderLeftColor: STORY_COLORS[shown.kind] }}>
        <span className="caption-time">{shown.time}</span>
        <span className="caption-dot" aria-hidden="true">
          ·
        </span>
        {shown.text}
      </div>
    </div>
  );
}
