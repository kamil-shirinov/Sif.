import { Effect } from "postprocessing";
import { Uniform, Vector3 } from "three";
import { vis } from "./vis";

// One colour grade for the whole scene, after filmic (ACES) tone mapping. Five looks blend by what the scene
// shows: calm, watch and storm (from the wind, which follows series.state), fair wind (vis.fairWind) and night
// (vis.dayFactor). The grade only shifts colour and contrast; it never hides or adds anything.

interface Look {
  lift: [number, number, number];
  gain: [number, number, number];
  sat: number;
  contrast: number;
  vignette: number;
}
const CALM: Look = { lift: [0.0, 0.006, 0.014], gain: [1.03, 1.01, 0.97], sat: 1.06, contrast: 1.03, vignette: 0.22 };
const WATCH: Look = { lift: [0.0, 0.01, 0.02], gain: [0.99, 0.99, 1.0], sat: 0.93, contrast: 1.06, vignette: 0.28 };
// Storm: cold and desaturated, with lifted shadows. (Extra contrast here crushed the dark sea to black.)
const STORM: Look = { lift: [0.014, 0.024, 0.034], gain: [0.95, 0.99, 1.05], sat: 0.82, contrast: 1.02, vignette: 0.32 };
// Fair wind is brighter and a touch warmer, never yellow: a strong warm gain turned the far sea tan.
const FAIR: Look = { lift: [0.004, 0.004, 0.004], gain: [1.05, 1.03, 0.99], sat: 1.1, contrast: 1.04, vignette: 0.2 };
const NIGHT: Look = { lift: [0.0, 0.01, 0.03], gain: [0.9, 0.97, 1.12], sat: 0.85, contrast: 1.05, vignette: 0.34 };

const FRAG = /* glsl */ `
uniform vec3 uLift;
uniform vec3 uGain;
uniform float uSat;
uniform float uContrast;
uniform float uVignette;
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec3 c = inputColor.rgb;
  float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = mix(vec3(l), c, uSat);
  c = (c - 0.5) * uContrast + 0.5;
  c = c * uGain + uLift * (1.0 - c);
  float d = length((uv - 0.5) * vec2(1.25, 1.0));
  c *= 1.0 - uVignette * smoothstep(0.32, 0.9, d);
  outputColor = vec4(max(c, 0.0), inputColor.a);
}`;

export class GradeEffect extends Effect {
  constructor() {
    super("GradeEffect", FRAG, {
      uniforms: new Map<string, Uniform>([
        ["uLift", new Uniform(new Vector3())],
        ["uGain", new Uniform(new Vector3(1, 1, 1))],
        ["uSat", new Uniform(1)],
        ["uContrast", new Uniform(1)],
        ["uVignette", new Uniform(0.25)],
      ]),
    });
  }

  /** Blend the looks from the shared visual state; call once per frame. */
  updateFromVis() {
    // Wind is 0.15 calm, 0.55 watch, 1.0 storm (smoothed series.state).
    const w = vis.wind;
    const watchW = Math.max(0, 1 - Math.abs(w - 0.55) / 0.4);
    const stormW = Math.min(1, Math.max(0, (w - 0.55) / 0.45));
    const calmW = Math.max(0, 1 - watchW - stormW);
    const night = 1 - vis.dayFactor;
    const fair = vis.fairWind;
    const weights: [Look, number][] = [
      [CALM, calmW * (1 - night) * (1 - fair)],
      [WATCH, watchW * (1 - night) * (1 - fair)],
      [STORM, stormW * (1 - night * 0.5) * (1 - fair)],
      [NIGHT, night * (1 - stormW * 0.5) * (1 - fair)],
      [FAIR, fair],
    ];
    let sum = 0;
    for (const [, k] of weights) sum += k;
    sum = sum || 1;
    const u = this.uniforms;
    const lift = u.get("uLift")!.value as Vector3;
    const gain = u.get("uGain")!.value as Vector3;
    lift.set(0, 0, 0);
    gain.set(0, 0, 0);
    let sat = 0;
    let con = 0;
    let vig = 0;
    for (const [L, k0] of weights) {
      const k = k0 / sum;
      lift.x += L.lift[0] * k;
      lift.y += L.lift[1] * k;
      lift.z += L.lift[2] * k;
      gain.x += L.gain[0] * k;
      gain.y += L.gain[1] * k;
      gain.z += L.gain[2] * k;
      sat += L.sat * k;
      con += L.contrast * k;
      vig += L.vignette * k;
    }
    // A lightning flash washes the grade out for its few frames.
    const f = vis.flash;
    u.get("uSat")!.value = sat * (1 - 0.35 * f);
    u.get("uContrast")!.value = con;
    u.get("uVignette")!.value = vig * (1 - 0.6 * f);
  }
}
