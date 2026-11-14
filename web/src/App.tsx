import { Component, lazy, Suspense, useCallback, useEffect, type ReactNode } from "react";
import { createAudioEngine } from "./audio/engine";
import { BundleError, loadBundle, stormIdFromUrl } from "./lib/loadBundle";
import { derive } from "./lib/derive";
import { useReplayDriver } from "./lib/useReplayDriver";
import { useApp } from "./state/app";
import { useTimeline } from "./state/timeline";
import { Hud } from "./ui/Hud";
import { Toasts } from "./ui/Toasts";
import { Manifest } from "./ui/Manifest";
import { MarketChart } from "./ui/MarketChart";
import { Controls } from "./ui/Controls";
import { ShipLabels } from "./ui/ShipLabels";

const StormScene = lazy(() => import("./scene/Scene").then((m) => ({ default: m.StormScene })));

const AUTOPLAY_MS = 2000;

// One engine for the page's lifetime (StrictMode remounts must not dispose it).
const audioEngine = createAudioEngine();
window.addEventListener("pagehide", () => audioEngine.dispose());

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

  // Load the bundle named by ?storm= (default mock_storm).
  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    useApp.getState().setWebglOk(hasWebGL());
    (async () => {
      try {
        const b = await loadBundle(stormIdFromUrl());
        if (cancelled) return;
        const d = derive(b);
        useApp.getState().setBundle(b, d);
        useTimeline.getState().reset(b.n);
        const params = new URLSearchParams(window.location.search);
        const at = Number(params.get("at"));
        if (params.has("at") && Number.isFinite(at)) useTimeline.getState().seek(at);
        if (params.get("autoplay") === "0") return;
        document.title = `StormScore · ${b.title}`;
        // Cold open: calm water, then auto-play.
        timer = window.setTimeout(() => useTimeline.getState().play(), AUTOPLAY_MS);
      } catch (e) {
        if (!cancelled) useApp.getState().setError(e instanceof BundleError ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

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
        useTimeline.getState().toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useReplayDriver(bundle, derived, audio);

  const onSceneError = useCallback(() => useApp.getState().setWebglOk(false), []);

  if (error) {
    return (
      <div className="fatal">
        <div className="wordmark">
          Storm<span>Score</span>
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
      <div className="overlay">
        {webglOk && <ShipLabels bundle={bundle} derived={derived} />}
        <Hud bundle={bundle} derived={derived} onSound={onSound} />
        <Toasts />
        <Manifest bundle={bundle} derived={derived} />
        <MarketChart bundle={bundle} derived={derived} large={!webglOk} />
        <Controls derived={derived} />
        {webglOk && <div className="hint">drag to orbit · scroll to zoom · double-click to reset</div>}
      </div>
    </div>
  );
}
