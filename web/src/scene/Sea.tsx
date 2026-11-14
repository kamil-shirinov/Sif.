import { useEffect, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Color, PlaneGeometry, Vector3 } from "three";
import { Water } from "three/examples/jsm/objects/Water.js";
import { makeWaterNormals } from "./waterNormals";
import { WAVE_GLSL, waveUniforms } from "./waves";
import { MOON_DIR, vis } from "./vis";

const SEA_SIZE = 9000;

const SEA_SEGMENTS = 480; // per side
const SEA_NEAR_STEP = 0.7; // grid spacing around the ships, fine enough for the shortest wave (3.1 units)
const SEA_NEAR_STEPS = 150; // steps of that size out from the centre: 105 units, the whole default view

/**
 * Plane whose grid is uniform and fine around the ships, then grows geometrically toward the horizon. (A power-law
 * grid put 4-unit triangles under a 38-unit camera: storm waves came out as facets.)
 */
function makeSeaGeometry(): PlaneGeometry {
  const half = SEA_SEGMENTS / 2;
  const far = half - SEA_NEAR_STEPS;
  const reach = SEA_SIZE / 2 - SEA_NEAR_STEP * SEA_NEAR_STEPS;
  // Growth factor g with sum_{k=1..far} step * g^k = reach (bisection).
  let lo = 1;
  let hi = 2;
  for (let it = 0; it < 60; it++) {
    const g = (lo + hi) / 2;
    let sum = 0;
    let st = SEA_NEAR_STEP;
    for (let k = 0; k < far; k++) {
      st *= g;
      sum += st;
    }
    if (sum < reach) lo = g;
    else hi = g;
  }
  const g = (lo + hi) / 2;
  const coord = new Float64Array(half + 1);
  let st = SEA_NEAR_STEP;
  for (let k = 1; k <= half; k++) {
    if (k > SEA_NEAR_STEPS) st *= g;
    coord[k] = coord[k - 1] + st;
  }
  const at = (u: number) => {
    const k = Math.round(Math.abs(u) * half);
    return Math.sign(u) * coord[Math.min(half, k)];
  };
  const geo = new PlaneGeometry(2, 2, SEA_SEGMENTS, SEA_SEGMENTS);
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) pos.setXY(i, at(pos.getX(i)), at(pos.getY(i)));
  geo.computeBoundingSphere();
  geo.computeBoundingBox();
  return geo;
}

const CALM_WATER = new Color("#1b4f66");
const STORM_WATER = new Color("#2a4b54");
// The designed colour of the sky as the sea sees it. The mirror reflection is pulled part of the way toward it
// (REFLECT_SHARE), so the water keeps a sea colour whatever the sky shader does (a turbid storm sky is tan).
const SKY_CALM = new Color("#8fa9bd");
const SKY_STORM = new Color("#46565f");
const SKY_NIGHT = new Color("#1c2b45");
const REFLECT_SHARE = 0.7;
const MOON_GLINT = new Color(0.34, 0.44, 0.6);

// Generated once per page: the sea remounts on quality changes, the texture does not need to.
let normalsCache: ReturnType<typeof makeWaterNormals> | null = null;
const waterNormals = () => (normalsCache ??= makeWaterNormals());

/** Whitecap cover 0..1 from risk: none below 0.15, full at 0.85. */
export const foamFromRisk = (risk: number) => Math.min(1, Math.max(0, (risk - 0.15) / 0.7));

const FOAM_GLSL = /* glsl */ `
float fHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float fNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(fHash(i), fHash(i + vec2(1, 0)), u.x), mix(fHash(i + vec2(0, 1)), fHash(i + vec2(1, 1)), u.x), u.y);
}
float foamNoise(vec2 p) { return 0.55 * fNoise(p) + 0.3 * fNoise(p * 2.3 + 7.1) + 0.15 * fNoise(p * 5.1 - 3.7); }
`;

export function Sea({ lowQuality, reflect }: { lowQuality: boolean; reflect: boolean }) {
  const water = useMemo(() => {
    const w = new Water(makeSeaGeometry(), {
      textureWidth: 512,
      textureHeight: 512,
      waterNormals: waterNormals(),
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
    m.uniforms.uFoam = { value: 0 };
    m.uniforms.uFoamLight = { value: 1 };
    m.uniforms.uSss = { value: new Color("#1f8a86") };
    m.vertexShader = m.vertexShader
      .replace("varying vec4 worldPosition;", `varying vec4 worldPosition;\nvarying vec3 vWaveN;\nvarying float vJac;\nvarying float vCrest;\n${WAVE_GLSL}`)
      .replace(
        "mirrorCoord = modelMatrix * vec4( position, 1.0 );",
        `vec4 wp = modelMatrix * vec4( position, 1.0 );
         vec3 wn; float wj;
         vec3 wd = waveDisp( wp.xz, wn, wj );
         wp.xyz += wd;
         vWaveN = wn; vJac = wj; vCrest = wd.y;
         mirrorCoord = wp;`,
      )
      .replace("vec4 mvPosition =  modelViewMatrix * vec4( position, 1.0 );", "vec4 mvPosition = viewMatrix * wp;");
    m.fragmentShader = m.fragmentShader
      .replace(
        "varying vec4 worldPosition;",
        `varying vec4 worldPosition;
varying vec3 vWaveN;
varying float vJac;
varying float vCrest;
uniform float uReflect;
uniform vec3 uSkyTint;
uniform float uWaveAmp;
uniform float uFoam;
uniform float uFoamLight;
uniform vec3 uSss;
${FOAM_GLSL}`,
      )
      .replace(
        "vec3 surfaceNormal = normalize( noise.xzy * vec3( 1.5, 1.0, 1.5 ) );",
        `vec3 wn = normalize( vWaveN );
         vec3 surfaceNormal = normalize( noise.xzy * vec3( 1.5, 1.0, 1.5 ) + vec3( wn.x, 0.0, wn.z ) / max( wn.y, 0.25 ) * 2.0 );`,
      )
      .replace(
        "vec3 reflectionSample = vec3( texture2D( mirrorSampler, mirrorCoord.xy / mirrorCoord.w + distortion ) );",
        // Low quality (no mirror pass): the sky tint stands in for the reflection.
        "vec3 reflectionSample = mix( uSkyTint, vec3( texture2D( mirrorSampler, mirrorCoord.xy / mirrorCoord.w + distortion ) ), uReflect );",
      )
      .replace("float rf0 = 0.02;", "float rf0 = 0.035;")
      // theta = max(dot(eye, n), 0) can exceed 1 by rounding: pow() of the negative 1 - theta is NaN on Apple GPUs.
      .replace("float theta = max( dot( eyeDirection, surfaceNormal ), 0.0 );", "float theta = clamp( dot( eyeDirection, surfaceNormal ), 0.0, 1.0 );")
      .replace(
        "vec3 albedo = mix( ( sunColor * diffuseLight * 0.3 + scatter ) * getShadowMask(), reflectionSample + specularLight, reflectance );",
        `float crestH = clamp( vCrest / max( uWaveAmp, 0.05 ), -1.0, 1.0 );
         // Light through the thin top of a wave: a teal glow on the crests.
         vec3 sss = uSss * smoothstep( 0.05, 1.0, crestH ) * ( 0.25 + 0.75 * pow( 1.0 - theta, 2.0 ) ) * uFoamLight;
         vec3 albedo = mix( ( sunColor * diffuseLight * 0.3 + scatter + sss ) * getShadowMask(), reflectionSample + specularLight, reflectance );`,
      )
      .replace(
        "vec3 outgoingLight = albedo;",
        `// Whitecaps where the Gerstner crests squeeze together (low Jacobian), broken up by noise; cover from risk.
         float fn = foamNoise( worldPosition.xz * 0.42 + vec2( time * 0.35, time * 0.12 ) );
         float squeeze = ( 1.0 - vJac ) * 1.25 + max( crestH, 0.0 ) * 0.3;
         float thr = 1.08 - 0.42 * uFoam;
         float foam = smoothstep( thr, thr + 0.22, squeeze + ( fn - 0.5 ) * 0.55 ) * uFoam;
         foam += smoothstep( 0.78, 0.97, fn ) * smoothstep( 0.55, 1.0, crestH ) * uFoam * 0.25;
         foam *= 0.55 + 0.45 * fn;
         foam *= 1.0 - smoothstep( 260.0, 760.0, distance );
         vec3 outgoingLight = mix( albedo, vec3( 0.86, 0.9, 0.92 ) * uFoamLight, clamp( foam, 0.0, 0.92 ) );`,
      );
    return w;
  }, []);

  // No mirror pass in low quality, or when the adaptive quality has dropped reflections: a flat sky tint instead.
  const mirror = reflect && !lowQuality;
  useEffect(() => {
    const original = water.onBeforeRender;
    if (!mirror) water.onBeforeRender = () => {};
    water.material.uniforms.uReflect.value = mirror ? REFLECT_SHARE : 0;
    return () => {
      water.onBeforeRender = original;
    };
  }, [mirror, water]);

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
    // By day the glitter path is the sun's; at night (and while the market is closed) the moon's.
    const night = 1 - vis.dayFactor;
    (u.sunDirection.value as Vector3).copy(vis.sunDir).lerp(MOON_DIR, night).normalize();
    const light = vis.dayFactor * (1 - 0.7 * vis.risk) + vis.flash * 1.5;
    (u.sunColor.value as Color).setScalar(Math.min(1.5, 0.04 + light)).lerp(MOON_GLINT, night * (1 - 0.6 * vis.risk));
    (u.waterColor.value as Color).copy(CALM_WATER).lerp(STORM_WATER, vis.risk);
    tmp.copy(SKY_CALM).lerp(SKY_STORM, vis.risk).multiplyScalar(vis.dayFactor);
    (u.uSkyTint.value as Color).copy(tmp).lerp(SKY_NIGHT, night);
    u.uFoam.value = foamFromRisk(vis.risk);
    u.uFoamLight.value = Math.min(1.6, 0.12 + 0.88 * vis.dayFactor * (1 - 0.55 * vis.risk) + vis.flash * 1.2 + 0.08 * vis.lantern);
  });

  return <primitive object={water} />;
}
