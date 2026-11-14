import { useEffect, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Color, PlaneGeometry, Vector3 } from "three";
import { Water } from "three/examples/jsm/objects/Water.js";
import { makeWaterNormals } from "./waterNormals";
import { WAVE_GLSL, waveUniforms } from "./waves";
import { vis } from "./vis";

const SEA_SIZE = 9000;

/** Plane whose vertices are packed densely near the ships and sparsely toward the horizon. */
function makeSeaGeometry(): PlaneGeometry {
  const g = new PlaneGeometry(2, 2, 320, 320);
  const pos = g.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    const y = pos.getY(i);
    pos.setXY(i, Math.sign(x) * Math.pow(Math.abs(x), 2.4) * (SEA_SIZE / 2), Math.sign(y) * Math.pow(Math.abs(y), 2.4) * (SEA_SIZE / 2));
  }
  g.computeBoundingSphere();
  g.computeBoundingBox();
  return g;
}

const CALM_WATER = new Color("#1d4f66");
const STORM_WATER = new Color("#0b1a20");
const SKY_CALM = new Color("#7d93a6");
const SKY_STORM = new Color("#1a232c");

export function Sea({ lowQuality }: { lowQuality: boolean }) {
  const water = useMemo(() => {
    const w = new Water(makeSeaGeometry(), {
      textureWidth: 512,
      textureHeight: 512,
      waterNormals: makeWaterNormals(),
      sunDirection: new Vector3(0, 1, 0),
      sunColor: 0xffffff,
      waterColor: CALM_WATER.getHex(),
      distortionScale: 3,
      fog: true,
    });
    w.rotation.x = -Math.PI / 2;
    const m = w.material;
    Object.assign(m.uniforms, waveUniforms);
    m.uniforms.uReflect = { value: 1 };
    m.uniforms.uSkyTint = { value: new Color("#7d93a6") };
    m.vertexShader = m.vertexShader
      .replace("varying vec4 worldPosition;", `varying vec4 worldPosition;\nvarying vec3 vWave;\n${WAVE_GLSL}`)
      .replace(
        "mirrorCoord = modelMatrix * vec4( position, 1.0 );",
        `vec4 wp = modelMatrix * vec4( position, 1.0 );
         vWave = waveEval( wp.xz );
         wp.y += vWave.x;
         mirrorCoord = wp;`,
      )
      .replace("vec4 mvPosition =  modelViewMatrix * vec4( position, 1.0 );", "vec4 mvPosition = viewMatrix * wp;");
    m.fragmentShader = m.fragmentShader
      .replace(
        "varying vec4 worldPosition;",
        "varying vec4 worldPosition;\nvarying vec3 vWave;\nuniform float uReflect;\nuniform vec3 uSkyTint;\nuniform float uWaveAmp;\nuniform float uWaveChop;",
      )
      .replace(
        "vec3 surfaceNormal = normalize( noise.xzy * vec3( 1.5, 1.0, 1.5 ) );",
        `vec3 surfaceNormal = normalize( noise.xzy * vec3( 1.5, 1.0, 1.5 ) + vec3( -vWave.y, 0.0, -vWave.z ) * 2.0 );`,
      )
      .replace(
        "vec3 reflectionSample = vec3( texture2D( mirrorSampler, mirrorCoord.xy / mirrorCoord.w + distortion ) );",
        "vec3 reflectionSample = mix( uSkyTint, vec3( texture2D( mirrorSampler, mirrorCoord.xy / mirrorCoord.w + distortion ) ), uReflect );",
      )
      .replace(
        "vec3 outgoingLight = albedo;",
        `float crest = vWave.x / max( uWaveAmp, 0.05 );
         float foam = smoothstep( 0.55, 1.0, crest + noise.x * 0.25 ) * clamp( uWaveChop * 0.8, 0.0, 0.85 );
         vec3 outgoingLight = mix( albedo, vec3( 0.75, 0.8, 0.82 ) * ( 0.35 + 0.65 * sunColor ), foam );`,
      );
    return w;
  }, []);

  // Low quality: skip the mirror render and use a flat sky tint instead of reflections.
  useEffect(() => {
    const original = water.onBeforeRender;
    if (lowQuality) water.onBeforeRender = () => {};
    water.material.uniforms.uReflect.value = lowQuality ? 0 : 1;
    return () => {
      water.onBeforeRender = original;
    };
  }, [lowQuality, water]);

  useEffect(() => () => {
    water.geometry.dispose();
    water.material.dispose();
  }, [water]);

  const tmp = useMemo(() => new Color(), []);
  useFrame(() => {
    const u = water.material.uniforms;
    u.time.value += vis.dt * (0.35 + 0.9 * vis.wind);
    u.size.value = 3.2 + vis.wave.chop * 2.5;
    u.distortionScale.value = 1.5 + vis.wave.chop * 4;
    (u.sunDirection.value as Vector3).copy(vis.sunDir);
    const light = vis.dayFactor * (1 - 0.8 * vis.risk) + vis.flash * 1.5;
    (u.sunColor.value as Color).setScalar(Math.min(1.5, 0.05 + light));
    (u.waterColor.value as Color).copy(CALM_WATER).lerp(STORM_WATER, vis.risk);
    tmp.copy(SKY_CALM).lerp(SKY_STORM, vis.risk);
    (u.uSkyTint.value as Color).copy(tmp).multiplyScalar(0.3 + 0.7 * vis.dayFactor);
  });

  return <primitive object={water} />;
}
