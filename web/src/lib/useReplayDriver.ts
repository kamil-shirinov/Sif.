import { useEffect } from "react";
import type { AudioEngine } from "../audio/engine";
import type { Bundle, BundleEvent } from "../types/bundle";
import type { Derived, TriggerSpec } from "./derive";
import { sampleAt, stepAt } from "./derive";
import { useTimeline } from "../state/timeline";
import { useApp } from "../state/app";
import { emitJump, emitSceneEvent } from "./bus";
import { fmtPct, fmtUtc } from "./format";

const MAX_CATCHUP_FRAMES = 30; // never fire a burst of more than this many frames at once

function toastFor(e: BundleEvent, b: Bundle): { title: string; text: string } {
  switch (e.type) {
    case "watch":
      return { title: "Storm watch", text: e.text };
    case "alarm":
      return { title: "Storm alarm", text: `${e.text}. ${e.move_ahead_pct.toFixed(1)}% of the move was still ahead.` };
    case "margin_call":
      return { title: `Margin call: ${b.ships[e.ship].label}`, text: e.text };
    case "all_clear":
      return { title: "All clear", text: e.text };
    case "squall":
      return { title: "Squall", text: e.text || "A sharp move against the book. No cut." };
    case "fair_wind":
      return { title: "Fair wind", text: e.text || "A sharp move in the book's favour. No trade." };
    case "cut":
      return { title: `${b.ships[e.ship ?? "prepared"].label}: cargo cut`, text: e.text || "Threw cargo overboard to protect the margin." };
    case "restore":
      return { title: `${b.ships[e.ship ?? "prepared"].label}: cargo restored`, text: e.text || "Hoisted the cargo back aboard." };
  }
}

/** Events the sound engine has a cue for. Squall, fair_wind and restore stay silent: its interface has no cue for them. */
const AUDIO_EVENTS = new Set(["watch", "alarm", "cut", "margin_call", "all_clear"]);

/** Jump strength for the sound engine: vol_ratio scaled so 10x normal is full strength. */
export const jumpStrength = (b: Bundle, i: number) => Math.min(1, Math.max(0.2, b.series.vol_ratio[i] / 10));

/**
 * One requestAnimationFrame loop for the replay, independent of WebGL:
 * advances the playhead, fires triggers for each frame crossed while playing, feeds the sound engine.
 */
export function useReplayDriver(bundle: Bundle | null, derived: Derived | null, audio: AudioEngine) {
  useEffect(() => {
    if (!bundle || !derived) return;
    let raf = 0;
    let last = performance.now();
    const start = useTimeline.getState();
    let prevFrame = start.t === 0 ? -1 : Math.floor(start.t);
    let prevEpoch = start.seekEpoch;

    const fire = (f: number, specs: TriggerSpec[]) => {
      const { pushToast } = useApp.getState();
      for (const s of specs) {
        if (s.kind === "jump") {
          const strength = jumpStrength(bundle, f);
          audio.trigger({ type: "jump", strength });
          emitJump({ frame: f, strength });
        } else if (s.kind === "cut") {
          audio.trigger({ type: "cut" });
          emitSceneEvent({ type: "cut", frame: f });
          const label = bundle.ships[s.ship].label;
          pushToast({ kind: "cut", title: `${label}: cargo cut`, text: `Threw ${Math.round(s.fraction * 100)}% of the cargo overboard to protect the margin.` });
        } else if (s.kind === "restore") {
          emitSceneEvent({ type: "restore", frame: f });
          pushToast({ kind: "restore", title: `${bundle.ships[s.ship].label}: cargo restored`, text: "Hoisted the cargo back aboard." });
        } else if (s.kind === "market") {
          // Equities: the market closes (prices hold) and reopens (the gap shows).
          if (s.open) {
            const gap = s.gapPct !== null ? `, ${fmtPct(s.gapPct, 2)} from the last price before the close` : "";
            pushToast({ kind: "market", title: "Market open", text: `Trading resumed at ${s.price.toFixed(derived.priceDecimals)}${gap}.` });
          } else {
            pushToast({ kind: "market", title: "Market closed", text: s.resumeAt !== null ? `Prices hold until trading resumes at ${fmtUtc(s.resumeAt)}.` : "Prices hold for the rest of the replay." });
          }
        } else {
          const e = s.event;
          if (AUDIO_EVENTS.has(e.type)) audio.trigger({ type: e.type } as Parameters<AudioEngine["trigger"]>[0]);
          emitSceneEvent({ type: e.type, frame: f });
          pushToast({ kind: e.type, ...toastFor(e, bundle) });
        }
      }
    };

    const loop = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const tl = useTimeline.getState();
      tl.advance(dt);
      const { t, seekEpoch } = useTimeline.getState();
      const cur = Math.min(derived.n - 1, Math.floor(t));
      if (seekEpoch !== prevEpoch) {
        prevEpoch = seekEpoch;
        prevFrame = cur;
        if (t === 0) prevFrame = -1;
      } else if (cur > prevFrame) {
        const from = Math.max(prevFrame + 1, cur - MAX_CATCHUP_FRAMES + 1);
        for (let f = from; f <= cur; f++) {
          const specs = derived.triggers.get(f);
          if (specs) fire(f, specs);
        }
        prevFrame = cur;
      }

      // Sound follows the market every animation frame.
      const ships = derived.ships;
      const afloat = ships.unprepared.marginCallI === null || t < ships.unprepared.marginCallI;
      // Survive mode: the player's ship is the only one; Replay: the "Ignored it" ship's heel while it is afloat.
      const heelShip = derived.player ?? (afloat ? ships.unprepared : ships.prepared);
      audio.update({
        risk: sampleAt(bundle.series.risk, t),
        volRatio: sampleAt(bundle.series.vol_ratio, t),
        state: stepAt(bundle.series.state, t) as 0 | 1 | 2,
        heel: sampleAt(heelShip.heelDeg, t),
        price: sampleAt(bundle.series.mid, t),
        minuteIndex: cur,
      });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [bundle, derived, audio]);
}
