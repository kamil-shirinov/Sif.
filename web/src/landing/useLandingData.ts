// The landing's two sources, fetched as they are on disk: index.json (its metrics, and which file is the headline
// storm) and the headline bundle. Read with the lenient readers in facts.ts, so a bundle the replay's strict
// validator would refuse still tells its story, and a missing file only hides its section.

import { useEffect, useState } from "react";
import { isWithheld, parseIndex } from "../lib/loadBundle";
import { HEADLINE_STORM_ID } from "../lib/session";
import { readMetrics, readStory, type LandingMetrics, type StoryFacts } from "./facts";

export interface LandingData {
  /** undefined while loading; null when index.json has no metrics or is missing. */
  metrics: LandingMetrics | null | undefined;
  /** undefined while loading; null when the headline bundle is missing or unreadable. */
  story: StoryFacts | null | undefined;
  /** True when the index lists the headline storm without its bundle (the public build: market data not redistributed). */
  storyWithheld?: boolean;
}

const bundlesUrl = (name: string) => `${import.meta.env.BASE_URL}bundles/${encodeURIComponent(name)}`;

async function getJson(url: string, signal: AbortSignal): Promise<unknown> {
  const res = await fetch(url, { cache: "no-cache", signal });
  if (!res.ok) throw new Error(`${url} returned HTTP ${res.status}`);
  return res.json();
}

export function useLandingData(): LandingData {
  const [data, setData] = useState<LandingData>({ metrics: undefined, story: undefined });
  useEffect(() => {
    const ctl = new AbortController();
    (async () => {
      let rawIndex: unknown = null;
      try {
        rawIndex = await getJson(bundlesUrl("index.json"), ctl.signal);
      } catch {
        /* no index: no figures, and the headline is fetched by its id */
      }
      if (ctl.signal.aborted) return;
      const metrics = readMetrics(rawIndex);
      setData((d) => ({ ...d, metrics }));
      const index = parseIndex(rawIndex);
      if (isWithheld(index, HEADLINE_STORM_ID)) {
        // No bundle in this build: say so instead of fetching a file that is not there.
        setData((d) => ({ ...d, story: null, storyWithheld: true }));
        return;
      }
      const file = index?.storms.find((s) => s.storm_id === HEADLINE_STORM_ID)?.file ?? `${HEADLINE_STORM_ID}.json`;
      let story: StoryFacts | null = null;
      try {
        story = readStory(await getJson(bundlesUrl(file), ctl.signal));
      } catch {
        story = null;
      }
      if (!ctl.signal.aborted) setData((d) => ({ ...d, story }));
    })();
    return () => ctl.abort();
  }, []);
  return data;
}
