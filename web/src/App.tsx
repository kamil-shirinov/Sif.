import { Component, lazy, Suspense, useCallback, useEffect, type ReactNode } from "react";
import { createAudioEngine } from "./audio/engine";
import { BundleError, DEFAULT_STORM_ID, isWithheld, loadBundle, loadIndex, stormIdFromUrl, WITHHELD_NOTE } from "./lib/loadBundle";
import { fetchCandles, fetchHealth } from "./lib/api";
import { applyBundle, COLD_OPEN_MS, defaultStorm } from "./lib/session";
import { useReplayDriver } from "./lib/useReplayDriver";
import { bindSurviveAudio, useSurviveDriver } from "./lib/surviveGame";
import { useSurvive } from "./state/survive";
import { SurvivePanel } from "./ui/SurvivePanel";
import { SurviveActions } from "./ui/SurviveActions";
import { SurviveCard } from "./ui/SurviveCard";
import { useApp } from "./state/app";
import { useTimeline } from "./state/timeline";
import { Hud } from "./ui/Hud";
import { Toasts } from "./ui/Toasts";
import { Manifest } from "./ui/Manifest";
import { MarketChart } from "./ui/MarketChart";
import { Controls } from "./ui/Controls";
import { ShipLabels } from "./ui/ShipLabels";
import { FrontLabels } from "./ui/FrontLabels";
import { StormPicker } from "./ui/StormPicker";
import { EvidenceCard } from "./ui/EvidenceCard";
import { NavigatorPanel } from "./ui/NavigatorPanel";
import { Landing } from "./landing/Landing";
import { usePresenterKeys } from "./landing/usePresenterKeys";
import { useTransition } from "./landing/transition";
import { useExplore } from "./landing/explore";
import { Explorer } from "./landing/Explorer";

const StormScene = lazy(() => import("./scene/Scene").then((m) => ({ default: m.StormScene })));

// One engine for the page's lifetime (StrictMode remounts must not dispose it).
const audioEngine = createAudioEngine();
window.addEventListener("pagehide", () => audioEngine.dispose());
bindSurviveAudio(audioEngine);

function hasWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

class SceneBoundary extends Component<{ onError: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(err: unknown) {
    console.error("3D scene failed, falling back to chart and HUD", err);
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export function App() {
  const bundle = useApp((s) => s.bundle);
  const derived = useApp((s) => s.derived);
  const error = useApp((s) => s.error);
  const lowQuality = useApp((s) => s.lowQuality);
  const webglOk = useApp((s) => s.webglOk);
  const audio = audioEngine;
  const mode = useApp((s) => s.mode);
  const sunkAnnounced = useSurvive((s) => s.phase === "sailing" && s.sunkAnnounced);
  const landing = useApp((s) => s.landing);
  // Landing <-> replay is one move (landing/transition.ts): while it runs, the page and the HUD are both mounted, one
  // leaving and the other arriving.
  const phase = useTransition((s) => s.phase);
  const preparing = useTransition((s) => s.preparing);
  const showLandingPage = landing || phase === "opening";
  // The HUD stays mounted under the landing page (hidden and inert), so opening the replay only starts its arrival:
  // mounting it then (the chart, the panels) cost a 60 ms frame at take-off.
  // The Explorer (Start) sits over the sea with the HUD hidden under it, like the landing page.
  const explorerOpen = useExplore((s) => s.open);
  const explorerLeaving = useExplore((s) => s.leaving);
  const hudClass =
    explorerOpen && phase !== "closing"
      ? "hud-hidden"
      : phase === "opening"
        ? "hud-arrive"
        : phase === "closing"
          ? "hud-leave"
          : landing
            ? "hud-hidden"
            : "";
  // The captions and the end card are portalled to <body> (ui/Presenter.tsx), outside the overlay: the phase is mirrored
  // on the root element so landing/transition.css can keep them out of the flight.
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("tr-hud-hidden", hudClass === "hud-hidden");
    root.classList.toggle("tr-hud-arrive", hudClass === "hud-arrive");
    root.classList.toggle("tr-hud-leave", hudClass === "hud-leave");
  }, [hudClass]);

  // Start: read index.json and ask the server for its health (both optional), then load the storm
  // named by ?storm=, else the largest move in the index, else mock_storm.
  useEffect(() => {
    let cancelled = false;
    const ctl = new AbortController();
    useApp.getState().setWebglOk(hasWebGL());
    void fetchHealth(ctl.signal).then((h) => {
      if (!cancelled) useApp.getState().setHealth(h);
    });
    (async () => {
      try {
        const index = await loadIndex();
        if (cancelled) return;
        useApp.getState().setIndex(index);
        const params = new URLSearchParams(window.location.search);
        if (params.get("mode") === "survive") useApp.getState().setMode("survive"); // ?mode=survive opens the game
        let named = stormIdFromUrl();
        let withheldNote: string | null = null;
        if (named !== null && isWithheld(index, named)) {
          // A link to a real storm on the public build: play the synthetic example and say why.
          withheldNote = `${named}: ${WITHHELD_NOTE}`;
          named = null;
        }
        let pick = named !== null ? { id: named, file: index?.storms.find((s) => s.storm_id === named)?.file } : defaultStorm(index);
        let b;
        try {
          b = await loadBundle(pick.id, pick.file);
        } catch (e) {
          // A default taken from the index may name a file that is not there: fall back to the synthetic example.
          if (named !== null || pick.id === DEFAULT_STORM_ID) throw e;
          pick = { id: DEFAULT_STORM_ID, file: undefined };
          b = await loadBundle(pick.id);
        }
        if (cancelled) return;
        const at = Number(params.get("at"));
        applyBundle(b, {
          // cold open: calm water, then auto-play; the landing page keeps the water calm until a storm is opened
          autoplayMs: params.get("autoplay") === "0" || useApp.getState().landing ? null : COLD_OPEN_MS,
          at: params.has("at") ? at : null,
        });
        if (withheldNote) useApp.getState().setLoadError(withheldNote);
        useApp.getState().setBaseStormId(b.storm_id);
      } catch (e) {
        if (!cancelled) useApp.getState().setError(e instanceof BundleError ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
      ctl.abort();
    };
  }, []);

  // With a live server (health.tiger), fetch the chart's candles for each bundle's window.
  const tiger = useApp((s) => s.health?.tiger === true);
  const bundleSeq = useApp((s) => s.bundleSeq);
  useEffect(() => {
    const { bundle: b } = useApp.getState();
    if (!tiger || !b) return;
    const ctl = new AbortController();
    useApp.getState().setLive(null, "loading");
    void fetchCandles(b, bundleSeq, ctl.signal).then((live) => {
      if (ctl.signal.aborted) return;
      useApp.getState().setLive(live, live ? "ok" : "failed");
    });
    return () => ctl.abort();
  }, [tiger, bundleSeq]);

  // Sound: start() on the first user gesture (browsers block audio before one).
  const startAudio = useCallback(async () => {
    const st = useApp.getState();
    if (st.audioStarted) return;
    st.setAudioStarted();
    try {
      await audio.start();
    } catch (e) {
      console.warn("Audio engine failed to start", e);
    }
    audio.setMuted(!useApp.getState().soundOn);
  }, [audio]);

  useEffect(() => {
    const onGesture = (e: Event) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest?.("[data-sound-toggle]")) return; // the sound button handles itself
      void startAudio();
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
    };
    window.addEventListener("pointerdown", onGesture);
    window.addEventListener("keydown", onGesture);
    return () => {
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
    };
  }, [startAudio]);

  const onSound = useCallback(() => {
    const st = useApp.getState();
    if (!st.audioStarted) {
      st.setSoundOn(true);
      void startAudio();
      return;
    }
    const next = !st.soundOn;
    st.setSoundOn(next);
    audio.setMuted(!next);
  }, [audio, startAudio]);

  // Space toggles play/pause.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement)) {
        e.preventDefault();
        // Survive: Space pauses and resumes a run; it never starts one (Sail does) or replays a finished one.
        if (useApp.getState().mode === "survive" && useSurvive.getState().phase !== "sailing") return;
        useTimeline.getState().toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  usePresenterKeys(); // L, 1, 2, 3, Esc (web/src/landing/keys.ts)
  useReplayDriver(bundle, derived, audio);
  useSurviveDriver();

  const onSceneError = useCallback(() => useApp.getState().setWebglOk(false), []);

  if (error) {
    return (
      <div className="fatal">
        <div className="wordmark" aria-label="Sif">
          Sif<span aria-hidden="true">.</span>
        </div>
        <p>Could not load the storm replay.</p>
        <pre>{error}</pre>
      </div>
    );
  }
  if (!bundle || !derived) return <div className="loading">Loading storm…</div>;

  return (
    <div className={`app ${webglOk ? "" : "no-webgl"}`}>
      {webglOk ? (
        <SceneBoundary onError={onSceneError}>
          <Suspense fallback={null}>
            <StormScene bundle={bundle} derived={derived} lowQuality={lowQuality} onError={onSceneError} />
          </Suspense>
        </SceneBoundary>
      ) : (
        <div className="no-webgl-note">3D view unavailable (WebGL failed). Showing the market chart and HUD.</div>
      )}
      {explorerOpen && <Explorer leaving={explorerLeaving || phase === "closing"} />}
      {showLandingPage && <Landing motion={phase === "opening" ? "leave" : phase === "closing" ? "enter" : null} />}
      {(
      <div className={`overlay ${hudClass}`} inert={hudClass === "hud-hidden"} aria-hidden={hudClass === "hud-hidden" || undefined}>
        {webglOk && <ShipLabels bundle={bundle} derived={derived} />}
        {webglOk && <FrontLabels bundle={bundle} derived={derived} />}
        <div className="stack stack-left">
          <Hud bundle={bundle} derived={derived} onSound={onSound} />
          {mode === "replay" && <StormPicker bundle={bundle} />}
          {mode === "replay" && <EvidenceCard />}
        </div>
        <Toasts derived={derived} />
        <div className="stack stack-right">
          {mode === "survive" ? (
            <SurvivePanel bundle={bundle} derived={derived} />
          ) : (
            <>
              <Manifest bundle={bundle} derived={derived} />
              <NavigatorPanel />
            </>
          )}
        </div>
        <MarketChart bundle={bundle} derived={derived} large={!webglOk} />
        {mode === "survive" && <SurviveActions />}
        {mode === "survive" && <SurviveCard bundle={bundle} />}
        {sunkAnnounced && <div className="sunk-vignette" aria-hidden="true" />}
        {/* Not under the landing page: Controls binds the presenter's H key and mounts the captions and end card, which
            belong to the replay (unmounting it there also ends the clean view, as L should). */}
        {(hudClass !== "hud-hidden" || preparing) && <Controls derived={derived} />}
        {webglOk && <div className="hint">drag to orbit · scroll to zoom · double-click to reset</div>}
      </div>
      )}
    </div>
  );
}
