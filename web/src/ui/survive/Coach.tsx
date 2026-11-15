import type { Bundle } from "../../types/bundle";
import type { SimResult } from "../../lib/survive";
import { coachLine, pastOf } from "./coach";

/** The coach's one line, from the frames played so far (coach.ts cuts the future off before it reads anything). */
export function Coach({ bundle, sim, frame }: { bundle: Bundle; sim: SimResult; frame: number }) {
  const line = coachLine(pastOf(bundle, sim, frame));
  return (
    <div className={`coach tone-${line.tone}`} data-kind={line.kind}>
      <span className="coach-who" aria-hidden="true">
        Coach
      </span>
      <span className="coach-text">{line.text}</span>
    </div>
  );
}
