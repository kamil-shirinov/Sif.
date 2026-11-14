import type { Derived } from "../lib/derive";
import { reopenFrame } from "../lib/derive";
import { fmtClock } from "../lib/format";
import { useFrameIndex } from "../state/timeline";

/** "Market closed" label while series.market_open is 0: night, prices hold, the replay fast-forwards to the reopening. */
export function MarketBanner({ derived }: { derived: Derived }) {
  const i = useFrameIndex();
  if (!derived.closed || derived.closed[i] !== 1) return null;
  const r = reopenFrame(derived, i);
  const resumes =
    r === null
      ? "closed for the rest of the replay"
      : `trading resumes ${fmtClock(derived.times[r])} UTC${derived.exchangeTz ? ` · ${fmtClock(derived.times[r], derived.solarOffsetS[r])} New York` : ""}`;
  return (
    <div className="market-banner" role="status">
      <span className="market-banner-title">Market closed</span>
      <span className="market-banner-sub">
        {resumes}
        {r !== null ? " · fast-forwarding the night" : ""}
      </span>
    </div>
  );
}
