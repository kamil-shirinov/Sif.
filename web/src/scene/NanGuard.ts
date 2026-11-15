import { Effect } from "postprocessing";
import { Uniform } from "three";

/** URL debug flags for checking the black-screen report on Apple GPUs (see README "Debug flags"). */
function param(name: string): string | null {
  try {
    return new URLSearchParams(window.location.search).get(name);
  } catch {
    return null;
  }
}
/** ?debug=nan: paint NaN / Inf pixels of the rendered scene magenta instead of zeroing them. */
export const DEBUG_NAN = param("debug") === "nan";
/** ?bloom=0: no EffectComposer at all (the renderer tone-maps directly, as in low quality). */
export const COMPOSER_ON = param("bloom") !== "0";

const FRAG = /* glsl */ `
uniform float uDebug;
bool bad(float x) { return isnan(x) || isinf(x) || !(abs(x) < 1e30); }
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec4 c = inputColor;
  bool b = bad(c.r) || bad(c.g) || bad(c.b) || bad(c.a);
  if (uDebug > 0.5) {
    outputColor = b ? vec4(1.0, 0.0, 1.0, 1.0) : c;
    return;
  }
  // Any NaN or Inf channel becomes 0; negative colour (no physical meaning, NaN in a later pow) becomes 0 too.
  c.r = bad(c.r) ? 0.0 : max(c.r, 0.0);
  c.g = bad(c.g) ? 0.0 : max(c.g, 0.0);
  c.b = bad(c.b) ? 0.0 : max(c.b, 0.0);
  c.a = bad(c.a) ? 1.0 : c.a;
  outputColor = c;
}`;

/**
 * First pass of the composer: one bad pixel must never reach the bloom, whose mip chain would spread it into
 * screen-sized black blocks. It runs as its own EffectPass so bloom (which reads its input before the effects of
 * its own pass run) sees the cleaned image.
 */
export class NanGuardEffect extends Effect {
  constructor() {
    super("NanGuardEffect", FRAG, { uniforms: new Map([["uDebug", new Uniform(DEBUG_NAN ? 1 : 0)]]) });
  }
}
