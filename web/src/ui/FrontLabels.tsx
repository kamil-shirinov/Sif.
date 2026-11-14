import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { useFrameIndex } from "../state/timeline";
import { fmtCountdown, fmtUtc, watchName } from "../lib/format";
import { labelEls } from "../scene/labels";

/**
 * One label per storm front, riding on the cloud wall (the scene positions it each frame and hides it
 * when the front is not on screen): the scheduled event's name and a countdown to the release,
 * e.g. "US Employment Situation in 12 min".
 */
export function FrontLabels({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  const i = useFrameIndex();
  return (
    <>
      {derived.watches.map((w, k) => {
        const minutes = ((w.at_i - i) * bundle.step_s) / 60;
        const when = minutes > 0 ? fmtCountdown(minutes) : minutes === 0 ? "now" : `· released ${Math.round(-minutes)} min ago`;
        return (
          <div
            key={k}
            className={`front-label ${minutes <= 0 ? "released" : ""}`}
            ref={(el) => {
              if (el) labelEls.set(`front-${k}`, el);
              else labelEls.delete(`front-${k}`);
            }}
          >
            <div className="front-label-main">
              {watchName(w)} {when}
            </div>
            <div className="front-label-sub">release {fmtUtc(derived.times[w.at_i], false)}</div>
          </div>
        );
      })}
    </>
  );
}
