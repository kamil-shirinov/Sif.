import { useEffect } from "react";
import { useApp } from "../state/app";
import { closeLanding, openHeadline, openNvda, openSurvive, showExplorer, showLanding, startExplorer } from "./actions";
import { bindPresenterKeys, type PresenterAction } from "./keys";

const RUN: Record<PresenterAction, () => void> = {
  landing: showLanding,
  headline: openHeadline,
  survive: openSurvive,
  nvda: openNvda,
  close: closeLanding,
  start: startExplorer,
  explore: showExplorer,
};

/** L, 1, 2, 3 and Esc for the presenter (keys.ts has the rules). Mounted once, in App. */
export function usePresenterKeys() {
  useEffect(
    () =>
      bindPresenterKeys(
        window,
        () => useApp.getState().landing,
        (a) => RUN[a](),
      ),
    [],
  );
}
