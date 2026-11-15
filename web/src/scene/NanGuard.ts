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

/** Brightest radiance the guard lets through. Lamps and lightning peak near 25; the bloom threshold is 6. */
const MAX_RADIANCE = 48;

const FRAG = /* glsl */ `
uniform float uDebug;
// Metal compiles shaders with fast math, which may assume there is no NaN or Inf and drop isnan() / isinf() and
// comparisons written to catch them. The bit pattern cannot be optimised away: exponent all ones is NaN or Inf.
bool bad(float x) { return (floatBitsToUint(x) & 0x7F800000u) == 0x7F800000u || abs(x) > 1.0e6; }
float clean(float x) { return bad(x) ? 0.0 : clamp(x, 0.0, ${MAX_RADIANCE.toFixed(1)}); }
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec4 c = inputColor;
  bool b = bad(c.r) || bad(c.g) || bad(c.b) || bad(c.a);
  if (uDebug > 0.5) {
    // Magenta: NaN or Inf. Yellow: finite but far too bright (it would overflow the bloom's half-float buffers).
    bool hot = max(c.r, max(c.g, c.b)) > ${MAX_RADIANCE.toFixed(1)};
    outputColor = b ? vec4(1.0, 0.0, 1.0, 1.0) : hot ? vec4(1.0, 1.0, 0.0, 1.0) : c;
    return;
  }
  // Any NaN or Inf channel becomes 0, negative colour (no physical meaning, NaN in a later pow) becomes 0, and
  // radiance is capped: a specular glint of 1e5 fits this pass but overflows to Inf in the bloom's half-float
  // mips, and tone mapping turns Inf into NaN, which is black.
  outputColor = vec4(clean(c.r), clean(c.g), clean(c.b), bad(c.a) ? 1.0 : c.a);
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
