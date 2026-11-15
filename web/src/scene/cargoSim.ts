import { Body, Box, Quaternion as CQuat, Vec3, World } from "cannon-es";
import { Matrix4, Quaternion, Vector3 } from "three";
import type { CrateSlot } from "./Ship";
import { BULWARK, DECK, HULL_B, HULL_H, HULL_L } from "./shipModel";

// The containers that go over the side at one cut, as one rigid-body simulation (cannon-es), run ahead of the playhead
// and stored as a table: the shove toward the rail, tipping over it, knocking into each other and the stowed boxes,
// falling, splashing, then floating with about 60% of their height under water until they have settled. The table is
// on calm water in the ship's resting pose; the live waves and the ship's own motion are added when it is drawn
// (Jettison.tsx). Because it is a table, every frame (playing at 1x or 4x, paused, scrubbed backwards) shows the
// same, physically settled boxes: none overlapping, none hanging through another.
//
// After the table ends the boxes drift as a group, away from the ship and with the wind, slowly spreading apart. Both
// are exact transforms (a translation and a scaling about the group's centre), so boxes that do not touch at the end of
// the simulation can never touch later.

/** Simulated seconds per replay frame: the replay's own pace at 1x (one market minute per 0.25 s). */
export const SIM_PER_FRAME = 0.25;
/** Fixed simulation step, and every how many steps a sample is stored. */
const STEP = 1 / 60;
const STORE_EVERY = 2;
/** Seconds simulated after the last box is cut loose: falling, splashing, coming to rest afloat. */
const SETTLE_S = 7.5;
const GRAVITY = 9.82;
/** Share of a box's height under water at rest: 40% freeboard shows. */
export const DRAFT = 0.6;
/** Collision boxes are this much larger than the drawn ones, so the drawn boxes always keep a gap between them. */
const MARGIN = 1.06;
const PUSH_ACCEL = 7;
/** Upward help for a box stuck on the rail or a neighbour (more than gravity: it is levered up and over). */
const STUCK_LIFT = 13;
/** After this long a box is no longer shoved (it is in the water by then). */
const PUSH_MAX_S = 6;
/** Strength of the push apart between floating boxes that are close, units / s^2 at contact. */
const SEPARATE = 2.2;
/** Per-step time budget for simulating ahead of the playhead in the background, ms per animation frame. */
export const BACKGROUND_BUDGET_MS = 3;

export interface SimCrate {
  /** Index into the Jettison plan. */
  k: number;
  slot: CrateSlot;
  /** Simulated seconds after the group's start when this box is cut loose. */
  release: number;
}

const _v = new Vec3();
const _w = new Vec3();
const _r = new Vec3();
const _f = new Vec3();
const _q = new CQuat();
const _tq = new Quaternion();

/** One cut's boxes, simulated on demand and stored. */
export class CutSim {
  readonly startFrame: number;
  readonly duration: number; // simulated seconds the table covers
  /** The ship's pose the table was made in (and its inverse): at rest, deck at the freeboard of the cut. */
  readonly nominal = new Matrix4();
  readonly nominalInv = new Matrix4();
  readonly crates: SimCrate[];
  /** Per box: samples of x, y, z, qx, qy, qz, qw, every STORE_EVERY steps. */
  readonly samples: Float32Array[];
  /** Per box: simulated time it first touched the water (Infinity: not yet), and where. */
  readonly wetAt: Float64Array;
  readonly wetPos: Float32Array;
  /** Per box: where it rests at the end of the table, and the group's centre there (for the drift). */
  readonly centre = new Vector3();
  private world: World | null;
  private bodies: Body[];
  private released: boolean[];
  private steps = 0;
  private readonly totalSteps: number;
  private readonly cells: Vec3[][];
  private readonly dims: { len: number; h: number; w: number }[];
  private readonly starboard = new Vec3();

  constructor(startFrame: number, crates: SimCrate[], obstacles: CrateSlot[], lay: { x: number; z: number; heading: number }, deckY: number) {
    this.startFrame = startFrame;
    this.crates = crates;
    const lastRelease = crates.reduce((m, c) => Math.max(m, c.release), 0);
    this.duration = lastRelease + SETTLE_S;
    this.totalSteps = Math.ceil(this.duration / STEP);
    const nSamples = Math.floor(this.totalSteps / STORE_EVERY) + 2;
    this.samples = crates.map(() => new Float32Array(nSamples * 7));
    this.wetAt = new Float64Array(crates.length).fill(Infinity);
    this.wetPos = new Float32Array(crates.length * 3);
    this.nominal.compose(new Vector3(lay.x, deckY, lay.z), new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), lay.heading), new Vector3(1, 1, 1));
    this.nominalInv.copy(this.nominal).invert();
    const qShip = new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), lay.heading);
    const toWorld = (x: number, y: number, z: number) => new Vector3(x, y, z).applyMatrix4(this.nominal);
    this.starboard.set(Math.sin(lay.heading), 0, Math.cos(lay.heading));

    const world = new World({ gravity: new Vec3(0, -GRAVITY, 0) });
    world.allowSleep = false;
    world.defaultContactMaterial.friction = 0.3;
    world.defaultContactMaterial.restitution = 0.04;
    const fixed = (cx: number, cy: number, cz: number, hx: number, hy: number, hz: number) => {
      const b = new Body({ mass: 0, type: Body.STATIC, shape: new Box(new Vec3(hx, hy, hz)) });
      const p = toWorld(cx, cy, cz);
      b.position.set(p.x, p.y, p.z);
      b.quaternion.set(qShip.x, qShip.y, qShip.z, qShip.w);
      world.addBody(b);
    };
    // The hull below the hatch (its sides are what floating boxes bump against), the rails, the bridge front and the
    // forecastle break.
    const hullTop = 0.16;
    fixed(0, (hullTop - HULL_H) / 2, 0, (HULL_L / 2) * 0.92, (hullTop + HULL_H) / 2, HULL_B / 2 - 0.1);
    for (const s of [-1, 1]) fixed(0, (BULWARK - 0.1) / 2, s * (HULL_B / 2 - 0.06), HULL_L / 2, (BULWARK + 0.1) / 2, 0.06);
    fixed(DECK.x0 - 0.75, 1.2, 0, 0.3, 1.2, HULL_B / 2);
    fixed(DECK.x1 + 0.6, 0.6, 0, 0.3, 0.6, HULL_B / 2);
    // The boxes that stay aboard.
    for (const s of obstacles) fixed(s.local.x, s.local.y, s.local.z, (s.dims.len / 2) * MARGIN, s.dims.h / 2, (s.dims.w / 2) * MARGIN);

    this.dims = crates.map((c) => c.slot.dims);
    this.bodies = crates.map((c) => {
      const { len, h, w } = c.slot.dims;
      const b = new Body({ mass: 0, type: Body.STATIC, shape: new Box(new Vec3((len / 2) * MARGIN, h / 2, (w / 2) * MARGIN)) });
      const p = toWorld(c.slot.local.x, c.slot.local.y, c.slot.local.z);
      b.position.set(p.x, p.y, p.z);
      b.quaternion.set(qShip.x, qShip.y, qShip.z, qShip.w);
      b.linearDamping = 0.02;
      b.angularDamping = 0.05;
      world.addBody(b);
      return b;
    });
    // Buoyancy is felt at the centres of the box's eight octants.
    this.cells = this.dims.map(({ len, h, w }) => {
      const pts: Vec3[] = [];
      for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) pts.push(new Vec3((sx * len) / 4, (sy * h) / 4, (sz * w) / 4));
      return pts;
    });
    this.released = crates.map(() => false);
    this.world = world;
    this.store(0);
  }

  /** Simulated seconds already in the table. */
  get simulated(): number {
    return this.steps * STEP;
  }

  get complete(): boolean {
    return this.steps >= this.totalSteps;
  }

  /** Simulate until `simT` (seconds after the start) is in the table; stop early when `budgetMs` has been spent. */
  advance(simT: number, budgetMs = Infinity) {
    const world = this.world;
    if (!world) return;
    const target = Math.min(this.totalSteps, Math.ceil(simT / STEP) + STORE_EVERY);
    const t0 = performance.now();
    while (this.steps < target) {
      this.step(world);
      if (budgetMs !== Infinity && performance.now() - t0 > budgetMs) break;
    }
    if (this.complete) this.finish();
  }

  private step(world: World) {
    const t = this.steps * STEP;
    for (let i = 0; i < this.bodies.length; i++) {
      const b = this.bodies[i];
      if (!this.released[i]) {
        if (t < this.crates[i].release) continue;
        this.released[i] = true;
        b.type = Body.DYNAMIC;
        b.mass = 1;
        b.updateMassProperties();
        b.aabbNeedsUpdate = true;
      }
      // The shove toward the starboard rail while still inboard. A box that hangs on the rail or on a neighbour (slow,
      // still inboard) gets lifted as well, as a crew would lever it up, so every box that is cut goes over the side.
      const sinceRelease = t - this.crates[i].release;
      if (this.wetAt[i] === Infinity && sinceRelease < PUSH_MAX_S) {
        _v.set(b.position.x, b.position.y, b.position.z);
        if (this.starboardOffset(_v) < HULL_B / 2 + 0.2) {
          const speed = Math.hypot(b.velocity.x, b.velocity.z);
          const stuck = sinceRelease > 0.6 && speed < 0.6;
          _f.set(this.starboard.x * PUSH_ACCEL, stuck ? STUCK_LIFT : 2.2, this.starboard.z * PUSH_ACCEL);
          b.applyForce(_f);
        }
      }
      // Buoyancy: the box as eight octants. Each carries an eighth of the lift a fully sunk box would have
      // (GRAVITY / DRAFT, so at rest DRAFT of it is under water), times the share of it below calm water at y = 0,
      // measured over its vertical extent in its current attitude: right for a box upright, on its side or upside down.
      const cells = this.cells[i];
      const { len, h, w } = this.dims[i];
      const e = b.quaternion;
      // Row y of the rotation matrix: the vertical half-extent of an octant is |R10| len/4 + |R11| h/4 + |R12| w/4.
      const r10 = 2 * (e.x * e.y + e.w * e.z);
      const r11 = 1 - 2 * (e.x * e.x + e.z * e.z);
      const r12 = 2 * (e.y * e.z - e.w * e.x);
      const half = Math.max(0.05, Math.abs(r10) * (len / 4) + Math.abs(r11) * (h / 4) + Math.abs(r12) * (w / 4));
      const full = GRAVITY / DRAFT / cells.length;
      let anyWet = false;
      for (const p of cells) {
        b.quaternion.vmult(p, _r);
        const cy = b.position.y + _r.y;
        const frac = Math.min(1, Math.max(0, (half - cy) / (2 * half)));
        if (frac <= 0) continue;
        anyWet = true;
        // Velocity of the octant's centre: v + w x r; the water damps it in proportion to how wet it is.
        b.angularVelocity.cross(_r, _w);
        const vy = b.velocity.y + _w.y;
        const vx = b.velocity.x + _w.x;
        const vz = b.velocity.z + _w.z;
        _f.set(-vx * 0.5 * frac, full * frac - vy * 1.6 * frac, -vz * 0.5 * frac);
        b.applyForce(_f, _r);
      }
      if (anyWet) {
        if (this.wetAt[i] === Infinity) {
          this.wetAt[i] = t;
          this.wetPos.set([b.position.x, 0, b.position.z], i * 3);
        }
        // The water takes the spin out.
        b.angularVelocity.scale(Math.exp(-STEP * 2.5), b.angularVelocity);
      }
    }
    // Afloat, boxes close together drift apart (the water between them, the wind on each a little different): a soft
    // push apart in the horizontal plane. It also slides off any box that came to rest on top of another.
    for (let i = 0; i < this.bodies.length; i++) {
      if (this.wetAt[i] === Infinity) continue;
      const a = this.bodies[i];
      for (let j = i + 1; j < this.bodies.length; j++) {
        if (this.wetAt[j] === Infinity) continue;
        const b = this.bodies[j];
        const dx = b.position.x - a.position.x;
        const dz = b.position.z - a.position.z;
        const dist = Math.hypot(dx, dz);
        const reach = 0.4 * (this.dims[i].len + this.dims[j].len);
        if (dist >= reach) continue;
        const ux = dist > 1e-4 ? dx / dist : 1;
        const uz = dist > 1e-4 ? dz / dist : 0;
        const f = SEPARATE * (1 - dist / reach);
        _f.set(-ux * f, 0, -uz * f);
        a.applyForce(_f);
        _f.set(ux * f, 0, uz * f);
        b.applyForce(_f);
      }
    }
    world.step(STEP);
    this.steps++;
    if (this.steps % STORE_EVERY === 0) this.store(this.steps / STORE_EVERY);
  }

  /** How far a world point is to starboard of the ship's centre line. */
  private starboardOffset(p: Vec3): number {
    const e = this.nominal.elements;
    return (p.x - e[12]) * this.starboard.x + (p.z - e[14]) * this.starboard.z;
  }

  private store(j: number) {
    for (let i = 0; i < this.bodies.length; i++) {
      const b = this.bodies[i];
      const s = this.samples[i];
      s.set([b.position.x, b.position.y, b.position.z, b.quaternion.x, b.quaternion.y, b.quaternion.z, b.quaternion.w], j * 7);
    }
  }

  private finish() {
    if (!this.world) return;
    const j = Math.floor(this.totalSteps / STORE_EVERY);
    this.store(j);
    this.store(j + 1);
    this.centre.set(0, 0, 0);
    for (const b of this.bodies) this.centre.x += b.position.x / this.bodies.length;
    for (const b of this.bodies) this.centre.z += b.position.z / this.bodies.length;
    this.world = null; // the simulation is done: free it
    this.bodies = [];
  }

  /**
   * Box `i` at `simT` seconds, in the calm-water table (world space, ship at rest). Interpolated between samples.
   * Past the end of the table it is the resting pose; the caller adds the drift.
   */
  sample(i: number, simT: number, pos: Vector3, quat: Quaternion) {
    const s = this.samples[i];
    const step = STEP * STORE_EVERY;
    const maxJ = Math.max(0, Math.floor(Math.min(this.steps, this.totalSteps) / STORE_EVERY));
    const x = Math.min(maxJ, Math.max(0, simT / step));
    const j0 = Math.min(maxJ, Math.floor(x));
    const j1 = Math.min(maxJ, j0 + 1);
    const u = j1 === j0 ? 0 : x - j0;
    const a = j0 * 7;
    const b = j1 * 7;
    pos.set(s[a] + (s[b] - s[a]) * u, s[a + 1] + (s[b + 1] - s[a + 1]) * u, s[a + 2] + (s[b + 2] - s[a + 2]) * u);
    quat.set(s[a + 3], s[a + 4], s[a + 5], s[a + 6]);
    if (u > 0) {
      _q.set(s[b + 3], s[b + 4], s[b + 5], s[b + 6]);
      quat.slerp(_tq.set(_q.x, _q.y, _q.z, _q.w), u);
    }
  }
}
