import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { BoxGeometry, CylinderGeometry, Euler, Mesh, MeshBasicMaterial, MeshStandardMaterial, Quaternion, Vector3 } from "three";
import { HOIST_FRAMES, shipOf, THROW_FRAMES, type Derived, type SceneShip } from "../lib/derive";
import { waveAt, type WaveSample } from "./waves";
import { vis } from "./vis";
import { crateSlots, SHIP_LAYOUT, shipPose } from "./Ship";
import { splash } from "./Particles";

const MAST_TOP = 8.4; // local height of the mast head (Ship.tsx: mast centre 4.2, height 8.4)
const MAST_X = -2.4; // local x of the mast
const SWING = 2.2; // how high a hoisted crate swings above its straight path

const _w: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };
const _p = new Vector3();
const _p0 = new Vector3();
const _a = new Vector3();
const _b = new Vector3();
const _q = new Quaternion();
const _e = new Euler();
const UP = new Vector3(0, 1, 0);
const smooth = (u: number) => u * u * (3 - 2 * u);

interface Floater {
  land: Vector3;
  drift: Vector3;
  spin: number;
  j: number;
}

/** Where a crate floats `d` frames after it landed, and how it lies on the swell. */
function floatAt(c: Floater, size: number, d: number, out: Vector3, rot: Euler) {
  out.copy(c.land).addScaledVector(c.drift, d);
  waveAt(out.x, out.z, vis.wave, _w);
  out.y = _w.h - size * 0.25 + Math.sin(vis.elapsed * 2 + c.j) * 0.06;
  rot.set(-Math.atan(_w.dhdz) * 0.9 + c.spin, c.spin * 0.6 + d * 0.004, Math.atan(_w.dhdx) * 0.9 + 2.2);
}

/**
 * Crates in the water. At each cut event a crate arcs over the side and drifts away; at each restore
 * event it is hoisted back aboard on a line from the mast head and lands on its place on deck.
 * One mesh per crate trip (derived.ships[ship].trips), so several cuts and restores per bundle just work.
 */
export function Jettison({ shipKey, derived }: { shipKey: SceneShip; derived: Derived }) {
  const ship = shipOf(derived, shipKey);
  const lay = SHIP_LAYOUT[shipKey];
  const slots = useMemo(() => crateSlots(derived.crates), [derived.crates]);
  const geo = useMemo(() => new BoxGeometry(1, 1, 1), []);
  const ropeGeo = useMemo(() => new CylinderGeometry(0.045, 0.045, 1, 5), []);
  const ropeMat = useMemo(() => new MeshBasicMaterial({ color: "#2b2622" }), []);
  const mats = useMemo(() => slots.map((s) => new MeshStandardMaterial({ color: s.color, roughness: 0.8 })), [slots]);
  useEffect(
    () => () => {
      mats.forEach((m) => m.dispose());
    },
    [mats],
  );

  // Precompute per-trip world-space start and landing points and randomness.
  const plan = useMemo(() => {
    const cos = Math.cos(lay.heading);
    const sin = Math.sin(lay.heading);
    const toWorld = (lx: number, lz: number) => new Vector3(lay.x + lx * cos + lz * sin, 0, lay.z - lx * sin + lz * cos);
    const side = new Vector3(sin, 0, cos); // ship's local +z: the side facing the camera
    const mast = toWorld(MAST_X, 0);
    return ship.trips
      .map((trip, j) => {
        const slot = slots[trip.crate];
        if (!slot) return null;
        const r1 = ((j * 7919) % 97) / 97;
        const r2 = ((j * 104729) % 89) / 89;
        const deck = toWorld(slot.local.x, slot.local.z); // y is the live deck height, set per frame
        const land = toWorld(slot.local.x + (r1 - 0.5) * 2.5, 2.2 + 2.2 + r2 * 4.5);
        const drift = side.clone().multiplyScalar(0.1 + 0.08 * r1).add(new Vector3(-0.05 + 0.1 * r2, 0, 0.02));
        return { trip, slot, deck, land, drift, mast, spin: (r1 - 0.5) * 6, j };
      })
      .filter((c): c is NonNullable<typeof c> => c !== null);
  }, [lay, slots, ship]);

  const refs = useRef<(Mesh | null)[]>([]);
  const ropes = useRef<(Mesh | null)[]>([]);
  const prevT = useRef(vis.t);

  useFrame(() => {
    const t = vis.t;
    // Splashes only while the replay plays forward through a landing (not on a seek): a crate hits the water, or
    // leaves it on a hoist line.
    const pt = prevT.current;
    prevT.current = t;
    const playing = t > pt && t - pt < 3;
    const deckY = shipPose[shipKey].y;
    for (let k = 0; k < plan.length; k++) {
      const c = plan[k];
      const m = refs.current[k];
      const rope = ropes.current[k];
      if (!m || !rope) continue;
      const { trip } = c;
      const age = t - trip.out;
      const hoistAge = trip.back === null ? -1 : t - trip.back;
      if (age < 0 || hoistAge >= HOIST_FRAMES) {
        m.visible = false;
        rope.visible = false;
        continue;
      }
      m.visible = true;
      const size = c.slot.spec.size;
      const startY = deckY + c.slot.local.y;
      if (playing) {
        const land = trip.out + THROW_FRAMES;
        if (pt < land && t >= land) {
          floatAt(c, size, 0, _p0, _e);
          splash(_p0.x, _p0.y, _p0.z, Math.min(1.6, size));
        } else if (trip.back !== null && pt < trip.back && t >= trip.back) {
          floatAt(c, size, Math.max(0, trip.back - trip.out - THROW_FRAMES), _p0, _e);
          splash(_p0.x, _p0.y, _p0.z, 0.4);
        }
      }

      if (age < THROW_FRAMES) {
        // Over the side: an arc from the deck to the water.
        const u = age / THROW_FRAMES;
        _p.set(c.deck.x, 0, c.deck.z).lerp(_a.set(c.land.x, 0, c.land.z), u);
        waveAt(_p.x, _p.z, vis.wave, _w);
        _p.y = startY * (1 - u) + (_w.h - size * 0.25) * u + Math.sin(Math.PI * u) * 3.2;
        m.position.copy(_p);
        m.rotation.set(u * c.spin, u * c.spin * 0.6, u * 2.2);
        rope.visible = false;
        continue;
      }

      // Drifting on the water (also where a hoisted crate starts from).
      if (hoistAge < 0) {
        floatAt(c, size, age - THROW_FRAMES, _p, _e);
        m.position.copy(_p);
        m.rotation.copy(_e);
        rope.visible = false;
        continue;
      }

      // Hoisted back aboard: up from the water, swung over the rail, lowered to its place on deck.
      const u = hoistAge / HOIST_FRAMES;
      const e = smooth(u);
      floatAt(c, size, Math.max(0, (trip.back as number) - trip.out - THROW_FRAMES), _p0, _e);
      _p.set(_p0.x + (c.deck.x - _p0.x) * e, 0, _p0.z + (c.deck.z - _p0.z) * e);
      _p.y = _p0.y + (startY - _p0.y) * e + Math.sin(Math.PI * u) * SWING;
      m.position.copy(_p);
      m.rotation.set(_e.x * (1 - e), _e.y * (1 - e) + lay.heading * e, _e.z * (1 - e));

      // The line from the mast head to the top of the crate.
      _a.set(c.mast.x, deckY + MAST_TOP, c.mast.z);
      _b.set(_p.x, _p.y + size * 0.5, _p.z);
      const len = _a.distanceTo(_b);
      rope.visible = len > 0.01;
      rope.position.copy(_a).add(_b).multiplyScalar(0.5);
      rope.scale.set(1, len, 1);
      _q.setFromUnitVectors(UP, _p.copy(_b).sub(_a).normalize());
      rope.quaternion.copy(_q);
    }
  });

  return (
    <>
      {plan.map((c, k) => (
        <group key={k}>
          <mesh
            ref={(m) => {
              refs.current[k] = m;
            }}
            geometry={geo}
            material={mats[c.trip.crate]}
            scale={c.slot.spec.size * 0.94}
            visible={false}
          />
          <mesh
            ref={(m) => {
              ropes.current[k] = m;
            }}
            geometry={ropeGeo}
            material={ropeMat}
            visible={false}
          />
        </group>
      ))}
    </>
  );
}
