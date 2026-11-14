import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import {
  BackSide,
  CircleGeometry,
  Color,
  CylinderGeometry,
  DirectionalLight,
  FogExp2,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  NormalBlending,
  PMREMGenerator,
  Scene,
  ShaderMaterial,
  SphereGeometry,
  type WebGLRenderTarget,
} from "three";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { MOON_DIR, vis } from "./vis";

const FOG_CALM = new Color("#b3c6d4");
const FOG_STORM = new Color("#39444e");
const FOG_NIGHT = new Color("#111b2e");
const DOME_TOP_STORM = new Color("#10161c");
const DOME_HORIZON_STORM = new Color("#2f3a44");
const DOME_TOP_NIGHT = new Color("#060a17");
const DOME_HORIZON_NIGHT = new Color("#16243f");
const COOL_WHITE = new Color("#e6eef5");
/** The storm takes at most this share of the daylight: a North Sea storm at noon is slate grey, not black. */
const STORM_DARK_MAX = 0.72;
const HEMI_SKY_NIGHT = new Color("#6d8cc0");
const HEMI_SEA_NIGHT = new Color("#1c2c42");
const SUN_WARM = new Color("#ffb070");
const SUN_WHITE = new Color("#fff4e6");
/** Sky radiance scale: keeps the HDR sky under the bloom threshold so only lamp and lightning glow. */
const SKY_BASE = 0.6;
/** Environment map: cube face size, how often it may be re-baked, and its strength as fill light. */
const ENV_SIZE = 64;
const ENV_MIN_INTERVAL_S = 0.4;
const ENV_INTENSITY = 1.35;
const HEMI_SKY_CALM = new Color("#c4d8ea");
const HEMI_SKY_STORM = new Color("#7f8b96");
const HEMI_SEA_CALM = new Color("#2c4a58");
const HEMI_SEA_STORM = new Color("#232b31");
const ENV_SEA_CALM = new Color("#1c4254");
const ENV_SEA_STORM = new Color("#101a20");
/** Radius of the horizon haze band (inside the storm dome, beyond everything in the scene). */
const HAZE_RADIUS = 3400;
/** Sky size. The sky is a sphere of radius SKY_SCALE / 2 (225,000) that follows the camera; the far plane (Scene.tsx: CAMERA_FAR) is 2,000,000. */
export const SKY_SCALE = 450_000;
/** Radius of the sky sphere: the camera sits at its centre (it follows the camera), far inside CAMERA_FAR. */
export const SKY_RADIUS = SKY_SCALE / 2;
/** ?sky=0 hides the sky (debugging the black-screen report on Apple GPUs). */
const SKY_ON = (() => {
  try {
    return new URLSearchParams(window.location.search).get("sky") !== "0";
  } catch {
    return true;
  }
})();

/** Replace one shader snippet, and fail loudly in development if three changed it (a silent no-op would undo a fix). */
function patch(src: string, from: string, to: string): string {
  if (!src.includes(from)) {
    console.warn("Sky shader patch did not apply:", from);
    return src;
  }
  return src.replace(from, to);
}

/**
 * NaN-proof the Sky fragment shader. On Apple GPUs acos/asin outside [-1, 1], atan(0, 0), pow() of a negative base and
 * huge values fed to the hash noise give NaN, and a NaN pixel goes black (and spreads through bloom).
 */
function sanitizeSkyShader(src: string): string {
  let f = src;
  f = patch(f, "uniform float cloudScale;", "uniform float cloudScale;\nuniform float uDim;");
  f = patch(
    f,
    "vec3 direction = normalize( vWorldPosition - cameraPosition );",
    "vec3 dirRaw = vWorldPosition - cameraPosition;\n\t\t\tvec3 direction = dirRaw / max( length( dirRaw ), 1e-6 );",
  );
  f = patch(f, "float zenithAngle = acos( max( 0.0, direction.y ) );", "float zenithAngle = acos( clamp( direction.y, 0.0, 1.0 ) );");
  f = patch(f, "float theta = acos( direction.y );", "float theta = acos( clamp( direction.y, -1.0, 1.0 ) );");
  f = patch(f, "float phi = atan( direction.z, direction.x );", "float phi = atan( direction.z, abs( direction.x ) + abs( direction.z ) < 1e-6 ? 1.0 : direction.x );");
  // Near the horizon direction.y -> 0 and the cloud plane projection runs to infinity; the noise of an infinite
  // coordinate is NaN, and mix(x, NaN, 0) is still NaN. The horizon fade hides clouds there anyway.
  f = patch(f, "vec2 cloudUV = direction.xz / ( direction.y * elevation );", "vec2 cloudUV = direction.xz / ( max( direction.y, 0.02 ) * elevation );");
  f = patch(f, "float silver = clamp( 0.51 / pow( 1.49 - cosTheta * 1.4, 1.5 ), 0.0, 3.0 );", "float silver = clamp( 0.51 / pow( max( 1.49 - cosTheta * 1.4, 0.05 ), 1.5 ), 0.0, 3.0 );");
  // Final colour: never negative (the cloud pass subtracts the sun glow, and pow() of a negative in the sRGB
  // transfer is NaN), never NaN or Inf.
  f = patch(
    f,
    "gl_FragColor = vec4( texColor, 1.0 );",
    `vec3 skyC = texColor * uDim;
\t\t\tskyC = vec3( skyC.r >= 0.0 && skyC.r < 1e5 ? skyC.r : 0.0, skyC.g >= 0.0 && skyC.g < 1e5 ? skyC.g : 0.0, skyC.b >= 0.0 && skyC.b < 1e5 ? skyC.b : 0.0 );
\t\t\tgl_FragColor = vec4( skyC, 1.0 );`,
  );
  return f;
}

/**
 * Sky (three.js Sky with its built-in clouds), sun light, fog, storm darkening and horizon haze.
 * risk -> darkness, cloud cover, fog; state -> wind (cloud speed); time of day -> sun.
 */
export function Atmosphere() {
  const { scene, camera, gl } = useThree();

  const sky = useMemo(() => {
    const s = new Sky();
    // three's Sky is a 12-triangle box pinned to the far plane (gl_Position.z = w). Triangles of that box that cross
    // the camera plane clip degenerately on some GPUs (Apple), giving NaN pixels that bloom spreads over the screen.
    // Draw the same material on a finely subdivided sphere instead, well inside the far plane, with normal depth.
    s.geometry.dispose();
    (s as Mesh).geometry = new SphereGeometry(1, 64, 32);
    s.scale.setScalar(SKY_RADIUS);
    // Never cull the sky: it surrounds the camera whatever the orbit, and a culling decision must not drop it.
    s.frustumCulled = false;
    s.visible = SKY_ON;
    const u = s.material.uniforms;
    u.turbidity.value = 4;
    u.rayleigh.value = 2.2;
    u.mieCoefficient.value = 0.004;
    u.mieDirectionalG.value = 0.8;
    u.cloudElevation.value = 0.55;
    u.cloudScale.value = 0.00025;
    // Storm dimming happens inside the sky shader (before tone mapping), so it works in HDR too.
    u.uDim = { value: 1 };
    // Normal depth. The main camera never needs a clamp (the sphere is far inside its far plane), but the water's mirror
    // camera uses an oblique near plane, which drags its far plane in: there, and only for vertices beyond the far
    // plane (always w > 0), depth is held just inside it. Vertices with w <= 0 are never touched, so clipping at the
    // camera plane stays the GPU's ordinary near-plane clip.
    s.material.vertexShader = patch(
      s.material.vertexShader,
      "gl_Position.z = gl_Position.w; // set z to camera.far",
      "if ( gl_Position.w > 0.0 ) gl_Position.z = min( gl_Position.z, gl_Position.w * 0.99999 );",
    );
    s.material.fragmentShader = sanitizeSkyShader(s.material.fragmentShader);
    return s;
  }, []);

  // Storm darkening dome: sits inside the sky box, alpha from risk (and night).
  const dome = useMemo(() => {
    const mat = new ShaderMaterial({
      uniforms: { uDark: { value: 0 }, uTop: { value: new Color("#10161c") }, uHorizon: { value: new Color("#2f3a44") } },
      vertexShader: /* glsl */ `
        varying vec3 vDir;
        void main() {
          vDir = normalize(position);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        uniform float uDark; uniform vec3 uTop; uniform vec3 uHorizon;
        varying vec3 vDir;
        void main() {
          float up = clamp(vDir.y, 0.0, 1.0);
          vec3 c = mix(uHorizon, uTop, smoothstep(0.0, 0.6, up));
          float a = uDark * mix(0.8, 1.0, smoothstep(0.0, 0.4, up));
          gl_FragColor = vec4(c, a);
        }`,
      side: BackSide,
      transparent: true,
      depthWrite: false,
      fog: false,
      blending: NormalBlending,
    });
    const m = new Mesh(new SphereGeometry(4200, 32, 16), mat);
    m.renderOrder = -1;
    m.frustumCulled = false;
    return m;
  }, []);

  // Horizon haze: a band of the fog colour that is opaque at the horizon line and thins out upward, so the far sea
  // (which the fog has already taken to the same colour) runs into the sky without an edge. It rides with the camera,
  // so its y = 0 is always the horizon as seen from wherever the camera is.
  const haze = useMemo(() => {
    const mat = new ShaderMaterial({
      uniforms: { uColor: { value: new Color() }, uAmount: { value: 0.9 }, uScale: { value: 0.03 } },
      vertexShader: /* glsl */ `
        varying float vUp;
        void main() {
          vUp = position.y / ${HAZE_RADIUS.toFixed(1)};
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor; uniform float uAmount; uniform float uScale;
        varying float vUp;
        void main() {
          // vUp is the tangent of the elevation above the horizon; below it the band stays full.
          float up = max(vUp, 0.0);
          float a = uAmount * (0.7 * exp(-up / uScale) + 0.3 * exp(-up / (uScale * 4.0)));
          gl_FragColor = vec4(uColor, clamp(a, 0.0, 1.0));
        }`,
      side: BackSide,
      transparent: true,
      depthWrite: false,
      fog: false,
    });
    const m = new Mesh(new CylinderGeometry(HAZE_RADIUS, HAZE_RADIUS, 2400, 64, 24, true), mat);
    m.renderOrder = -1;
    m.frustumCulled = false;
    return m;
  }, []);

  // Image-based fill light: the sky itself, prefiltered (PMREM) into scene.environment, so every PBR surface is lit
  // and reflects the sky it stands under: blue and bright on a calm day, grey and dim in a storm, dark at night.
  // The probe scene holds the same sky material (so it follows risk, sun and cloud) and a disc for the sea below.
  const probe = useMemo(() => {
    const s = new Scene();
    const dome = new Mesh(new SphereGeometry(1, 32, 16), sky.material);
    dome.scale.setScalar(900);
    dome.frustumCulled = false;
    const seaMat = new MeshBasicMaterial({ color: "#16323f" });
    const sea = new Mesh(new CircleGeometry(880, 24), seaMat);
    sea.rotation.x = -Math.PI / 2;
    sea.position.y = -2;
    s.add(dome, sea);
    return { scene: s, seaMat, pmrem: new PMREMGenerator(gl), target: null as WebGLRenderTarget | null, key: "", last: -1e9 };
  }, [sky, gl]);
  useEffect(
    () => () => {
      scene.environment = null;
      probe.target?.dispose();
      probe.pmrem.dispose();
    },
    [scene, probe],
  );

  const fog = useMemo(() => new FogExp2(FOG_CALM.getHex(), 0.0006), []);
  useEffect(() => {
    scene.fog = fog;
    return () => {
      scene.fog = null;
    };
  }, [scene, fog]);

  const sunRef = useRef<DirectionalLight>(null);
  const hemiRef = useRef<HemisphereLight>(null);
  const moonRef = useRef<DirectionalLight>(null);
  const tmp = useMemo(() => new Color(), []);

  useFrame(() => {
    // The sky box rides with the camera, so wherever the camera is (orbit, pan, zoom) it sits at the box's centre:
    // no face or corner can come near it. The sky shader looks along (vertex - camera), which the move does not change.
    sky.position.copy(camera.position);
    const u = sky.material.uniforms;
    // A fair_wind event thins the cloud: the sky reads as if risk had dropped, so the sun breaks through.
    const fw = vis.fairWind;
    const r = vis.risk * (1 - 0.55 * fw);
    u.sunPosition.value.copy(vis.sunDir);
    u.time.value = vis.elapsed;
    u.cloudCoverage.value = 0.18 + 0.8 * r;
    u.cloudDensity.value = 0.25 + 0.7 * r;
    u.cloudSpeed.value = 0.00002 + 0.00012 * vis.wind;
    // Turbidity stays modest: a very turbid Preetham sky is tan at the horizon, and the sea reflects it.
    u.turbidity.value = 3.5 + 4 * r;
    u.rayleigh.value = 2.2 + 0.4 * r;
    u.showSunDisc.value = r < 0.6 ? 1 : 0;

    const night = 1 - vis.dayFactor;
    const dark = Math.min(0.92, STORM_DARK_MAX * (0.85 * r * r + 0.15 * r) + 0.3 * night) * (1 - 0.85 * vis.flash);
    u.uDim.value = SKY_BASE * (Math.max(0.03, 1 - dark) + vis.flash * 0.6);
    // The dome is the storm's slate overcast by day and a deep blue sky at night (the sky shader is black once the
    // sun is down), so the night has a horizon and the sea something to reflect.
    const dm = (dome.material as ShaderMaterial).uniforms;
    dm.uDark.value = Math.max(dark * 0.8, night * 0.9 * (1 - 0.85 * vis.flash));
    dm.uTop.value.copy(DOME_TOP_STORM).lerp(DOME_TOP_NIGHT, night);
    dm.uHorizon.value.copy(DOME_HORIZON_STORM).lerp(DOME_HORIZON_NIGHT, night);

    fog.color.copy(FOG_CALM).lerp(FOG_STORM, Math.min(1, r * 1.1)).lerp(FOG_NIGHT, night);
    fog.color.lerp(COOL_WHITE, vis.flash * 0.35 + fw * 0.1 * vis.dayFactor);
    // Calm: clear around the ships, and the sea has reached the fog colour where it meets the haze band.
    fog.density = 0.00055 + 0.0026 * r * r + 0.0006 * r;
    haze.position.copy(camera.position);
    const hz = (haze.material as ShaderMaterial).uniforms;
    hz.uColor.value.copy(fog.color);
    hz.uAmount.value = 0.94;
    hz.uScale.value = 0.022 + 0.06 * r;

    if (sunRef.current) {
      const s = sunRef.current;
      s.position.copy(vis.sunDir).multiplyScalar(120);
      s.intensity = 2.4 * vis.dayFactor * (1 - 0.62 * r) + vis.flash * 5 + fw * 1.6 * Math.max(0.3, vis.dayFactor);
      tmp.copy(SUN_WARM).lerp(SUN_WHITE, Math.min(1, vis.sunDir.y * 3));
      s.color.copy(tmp);
    }
    if (moonRef.current) {
      // Moonlight at night (and while the market is closed): enough to read both ships, dimmed by storm cloud.
      moonRef.current.position.copy(MOON_DIR).multiplyScalar(120);
      moonRef.current.intensity = 1.5 * night * (1 - 0.6 * r);
    }
    if (hemiRef.current) {
      // Sky fill from above, sea bounce from below. The environment map carries the colour; this keeps a floor
      // under it so shaded faces never go black, by day, in a storm or at night.
      const h = hemiRef.current;
      h.intensity = 0.34 + 0.75 * vis.dayFactor * (1 - 0.3 * r) + 0.7 * night + vis.flash * 2.5;
      h.color.copy(HEMI_SKY_CALM).lerp(HEMI_SKY_STORM, r).lerp(HEMI_SKY_NIGHT, night);
      h.groundColor.copy(HEMI_SEA_CALM).lerp(HEMI_SEA_STORM, r).lerp(HEMI_SEA_NIGHT, night);
    }

    // Re-bake the environment when the sky has changed enough to see (risk, sun, daylight, fair wind), at most
    // every 0.4 s. Lightning does not re-bake: it is brief, and the sun light and the hemisphere carry the flash.
    const key = `${Math.round(r * 24)}|${Math.round(vis.dayFactor * 16)}|${Math.round(vis.sunDir.x * 10)}|${Math.round(vis.sunDir.y * 12)}`;
    if (key !== probe.key && vis.elapsed - probe.last > ENV_MIN_INTERVAL_S) {
      probe.key = key;
      probe.last = vis.elapsed;
      const disc = u.showSunDisc.value;
      const dim = u.uDim.value;
      // No sun disc in the probe (the directional light is the sun), and no flash.
      u.showSunDisc.value = 0;
      u.uDim.value = SKY_BASE * Math.max(0.03, 1 - Math.min(0.92, STORM_DARK_MAX * (0.85 * r * r + 0.15 * r) + 0.3 * night));
      probe.seaMat.color.copy(ENV_SEA_CALM).lerp(ENV_SEA_STORM, r).multiplyScalar(0.08 + 0.92 * vis.dayFactor);
      const next = probe.pmrem.fromScene(probe.scene, 0, 1, 4000, { size: ENV_SIZE });
      u.showSunDisc.value = disc;
      u.uDim.value = dim;
      scene.environment = next.texture;
      probe.target?.dispose();
      probe.target = next;
    }
    scene.environmentIntensity = ENV_INTENSITY * (1 + vis.flash * 1.5);
  });

  return (
    <>
      <primitive object={sky} />
      <primitive object={dome} />
      <primitive object={haze} />
      <directionalLight ref={sunRef} intensity={2} />
      <directionalLight ref={moonRef} intensity={0} color="#a9c0ea" />
      <hemisphereLight ref={hemiRef} args={["#b8cde0", "#1b2a33", 0.8]} />
    </>
  );
}

