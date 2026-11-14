import { useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Bloom, EffectComposer, ToneMapping } from "@react-three/postprocessing";
import { ToneMappingMode } from "postprocessing";
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

/** Far plane well beyond the sky box's corners (SKY_SCALE x sqrt(3) / 2), so nothing of the sky can be clipped. */
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

function World({ bundle, derived, lowQuality }: { bundle: Bundle; derived: Derived; lowQuality: boolean }) {
  // Each loaded bundle (a new storm, a scenario) remounts what holds per-bundle state; the canvas stays.
  const seq = useApp((s) => s.bundleSeq);
  return (
    <>
      <VisDriver bundle={bundle} derived={derived} />
      <Atmosphere />
      <Sea lowQuality={lowQuality} />
      <StormFronts key={`f${seq}`} watches={derived.watches} />
      <Lighthouse />
      <SunBreak />
      {derived.player ? (
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
      <Rain lowQuality={lowQuality} />
      <Lightning />
      <CameraRig />
      {!lowQuality && (
        <EffectComposer multisampling={4}>
          <Bloom mipmapBlur luminanceThreshold={6} luminanceSmoothing={0.5} intensity={1.15} radius={0.75} />
          <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
        </EffectComposer>
      )}
    </>
  );
}

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
  return (
    <Canvas
      className="scene-canvas"
      dpr={lowQuality ? 1 : [1, 1.75]}
      camera={{ position: HOME_POS.toArray(), fov: 50, near: 0.5, far: CAMERA_FAR }}
      gl={{ antialias: lowQuality ? false : true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.toneMapping = ACESFilmicToneMapping;
        gl.toneMappingExposure = 0.55;
        gl.getContext().canvas.addEventListener("webglcontextlost", onError);
      }}
    >
      <World bundle={bundle} derived={derived} lowQuality={lowQuality} />
    </Canvas>
  );
}
