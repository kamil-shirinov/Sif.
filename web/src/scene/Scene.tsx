import { useEffect, useMemo, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer, ToneMapping } from "@react-three/postprocessing";
import { EffectPass, ToneMappingMode } from "postprocessing";
import { ACESFilmicToneMapping } from "three";
import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { onSceneEvent } from "../lib/bus";
import { useApp } from "../state/app";
import { playhead } from "../state/timeline";
import { pulseFairWind, pulseSquall, updateVis } from "./vis";
import { Sea } from "./Sea";
import { Atmosphere, SKY_SCALE } from "./Atmosphere";
import { Rain } from "./Rain";
import { Lightning } from "./Lightning";
import { StormFronts } from "./StormFront";
import { Lighthouse } from "./Lighthouse";
import { SunBreak } from "./SunBreak";
import { Ship } from "./Ship";
import { Jettison } from "./Jettison";
import { CameraRig, HOME_POS } from "./CameraRig";
import { PerformanceMonitor } from "@react-three/drei";
import { GradeEffect } from "./Grade";
import { COMPOSER_ON, NanGuardEffect } from "./NanGuard";
import { Clouds } from "./Clouds";
import { Stars } from "./Stars";
import { Particles } from "./Particles";
import { Stats, statsEnabled } from "./Stats";
import { show } from "./debugFlags";

/** Far plane well beyond the sky sphere (radius SKY_SCALE / 2), so nothing of the sky can be clipped. */
const CAMERA_FAR = 2_000_000;
if (CAMERA_FAR < SKY_SCALE * 2) throw new Error("camera far plane must stay well beyond the sky box");

function VisDriver({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  // The replay announces squall and fair_wind events it crosses while playing: a wall-clock pulse keeps them visible at high speed.
  useEffect(
    () =>
      onSceneEvent(({ type }) => {
        if (type === "squall") pulseSquall();
        else if (type === "fair_wind") pulseFairWind();
      }),
    [],
  );
  // Runs before every other useFrame: turns the playhead into shared visual state.
  useFrame((_, dt) => updateVis(bundle, derived, playhead(), Math.min(dt, 0.1)), -1);
  return null;
}

/**
 * Adaptive quality (high-quality path only). drei's PerformanceMonitor watches the frame rate and steps the tier down
 * when it falls under the display's rate, up when it recovers. Each step trades the least visible thing first.
 *   3: pixel ratio up to 1.75, MSAA, reflections, bloom
 *   2: pixel ratio 1.35, no MSAA
 *   1: pixel ratio 1, no mirror reflection (sky tint instead)
 *   0: pixel ratio 0.85, no bloom
 * "Low quality" (the HUD checkbox) is the separate fixed path: pixel ratio 1, no post-processing, no reflections.
 */
export const TIERS = [
  { dpr: 0.85, msaa: 0, reflect: false, bloom: false },
  { dpr: 1, msaa: 0, reflect: false, bloom: true },
  { dpr: 1.35, msaa: 0, reflect: true, bloom: true },
  { dpr: 1.75, msaa: 4, reflect: true, bloom: true },
] as const;

function Post({ tier }: { tier: number }) {
  const camera = useThree((s) => s.camera);
  const grade = useMemo(() => new GradeEffect(), []);
  // The NaN guard is its own pass, first, so bloom never sees a NaN or Inf pixel.
  const guard = useMemo(() => new EffectPass(camera, new NanGuardEffect()), [camera]);
  useEffect(() => () => guard.dispose(), [guard]);
  useFrame(() => grade.updateFromVis());
  const t = TIERS[tier];
  return (
    <EffectComposer key={`${OVERRIDE.msaa ?? t.msaa}-${t.bloom}`} multisampling={OVERRIDE.msaa ?? t.msaa}>
      <primitive object={guard} />
      {t.bloom ? <Bloom mipmapBlur luminanceThreshold={6} luminanceSmoothing={0.5} intensity={1.15} radius={0.75} /> : <></>}
      <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
      <primitive object={grade} />
    </EffectComposer>
  );
}

function World({ bundle, derived, lowQuality, tier }: { bundle: Bundle; derived: Derived; lowQuality: boolean; tier: number }) {
  // Each loaded bundle (a new storm, a scenario) remounts what holds per-bundle state; the canvas stays.
  const seq = useApp((s) => s.bundleSeq);
  return (
    <>
      <VisDriver bundle={bundle} derived={derived} />
      <Atmosphere />
      {show("clouds") && <Clouds lowQuality={lowQuality} />}
      {show("stars") && <Stars />}
      {show("sea") && <Sea lowQuality={lowQuality} reflect={TIERS[tier].reflect} />}
      {show("front") && <StormFronts key={`f${seq}`} watches={derived.watches} />}
      {show("lighthouse") && <Lighthouse />}
      {show("sunbreak") && <SunBreak />}
      {!show("ships") ? null : derived.player ? (
        // Survive mode: one ship, the player's.
        <>
          <Ship key={`y${seq}`} shipKey="player" derived={derived} />
          <Jettison key={`jy${seq}`} shipKey="player" derived={derived} />
        </>
      ) : (
        <>
          <Ship key={`p${seq}`} shipKey="prepared" derived={derived} />
          <Ship key={`u${seq}`} shipKey="unprepared" derived={derived} />
          <Jettison key={`jp${seq}`} shipKey="prepared" derived={derived} />
          <Jettison key={`ju${seq}`} shipKey="unprepared" derived={derived} />
        </>
      )}
      {show("particles") && <Particles />}
      {show("rain") && <Rain lowQuality={lowQuality} />}
      {show("lightning") && <Lightning />}
      <CameraRig />
      {statsEnabled && <Stats quality={lowQuality ? "low" : `tier ${tier}`} />}
      {!lowQuality && COMPOSER_ON && <Post tier={tier} />}
    </>
  );
}

/** ?msaa=<samples> and ?dpr=<ratio> override the tier's values (for measuring what each costs on a real GPU). */
const OVERRIDE = (() => {
  try {
    const q = new URLSearchParams(window.location.search);
    const msaa = q.has("msaa") ? Number(q.get("msaa")) : NaN;
    const dpr = q.has("dpr") ? Number(q.get("dpr")) : NaN;
    return { msaa: Number.isFinite(msaa) && msaa >= 0 && msaa <= 8 ? Math.round(msaa) : null, dpr: Number.isFinite(dpr) && dpr >= 0.5 && dpr <= 3 ? dpr : null };
  } catch {
    return { msaa: null, dpr: null };
  }
})();

/** ?tier=0..3 pins the quality tier (no adaptive changes), for measuring like with like. */
const PINNED_TIER = (() => {
  try {
    const v = Number(new URLSearchParams(window.location.search).get("tier"));
    return Number.isInteger(v) && v >= 0 && v < TIERS.length && new URLSearchParams(window.location.search).has("tier") ? v : null;
  } catch {
    return null;
  }
})();

const maxDpr = () => Math.min(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1, 1.75);

export function StormScene({
  bundle,
  derived,
  lowQuality,
  onError,
}: {
  bundle: Bundle;
  derived: Derived;
  lowQuality: boolean;
  onError: () => void;
}) {
  const [tier, setTier] = useState(PINNED_TIER ?? 3);
  const dpr = lowQuality ? 1 : Math.min(OVERRIDE.dpr ?? maxDpr(), OVERRIDE.dpr ?? TIERS[tier].dpr);
  return (
    <Canvas
      className="scene-canvas"
      dpr={dpr}
      camera={{ position: HOME_POS.toArray(), fov: 50, near: 0.5, far: CAMERA_FAR }}
      gl={{ antialias: lowQuality ? false : true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.toneMapping = ACESFilmicToneMapping;
        gl.toneMappingExposure = 0.55;
        gl.getContext().canvas.addEventListener("webglcontextlost", onError);
      }}
    >
      {!lowQuality && PINNED_TIER === null && (
        <PerformanceMonitor
          flipflops={4}
          onDecline={() => setTier((t) => Math.max(0, t - 1))}
          onIncline={() => setTier((t) => Math.min(TIERS.length - 1, t + 1))}
          onFallback={() => setTier(0)}
        />
      )}
      <World bundle={bundle} derived={derived} lowQuality={lowQuality} tier={lowQuality ? 0 : tier} />
    </Canvas>
  );
}
