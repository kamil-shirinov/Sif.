import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { BoxGeometry, Mesh, MeshStandardMaterial, Vector3 } from "three";
import type { ShipKey } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { waveAt, type WaveSample } from "./waves";
import { vis } from "./vis";
import { crateSlots, SHIP_LAYOUT, thrownCount, throwFrame } from "./Ship";

const FLIGHT_FRAMES = 2.2;
const _w: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };

/** Crates thrown overboard at cut_i (cut_fraction of the cargo). They arc over the side and drift away. */
export function Jettison({ shipKey, derived }: { shipKey: ShipKey; derived: Derived }) {
  const ship = derived.ships[shipKey];
  const lay = SHIP_LAYOUT[shipKey];
  const slots = useMemo(() => crateSlots(derived.crates), [derived.crates]);
  const n = thrownCount(ship, slots.length);
  const geo = useMemo(() => new BoxGeometry(1, 1, 1), []);

  // Precompute start/landing points and per-crate randomness in world space.
  const plan = useMemo(() => {
    const cos = Math.cos(lay.heading);
    const sin = Math.sin(lay.heading);
    const toWorld = (lx: number, lz: number) => new Vector3(lay.x + lx * cos + lz * sin, 0, lay.z - lx * sin + lz * cos);
    const side = new Vector3(sin, 0, cos); // ship's local +z: the side facing the camera
    return Array.from({ length: n }, (_, j) => {
      const slot = slots[slots.length - 1 - j];
      const r1 = ((j * 7919) % 97) / 97;
      const r2 = ((j * 104729) % 89) / 89;
      const start = toWorld(slot.local.x, slot.local.z);
      start.y = 0.6 + slot.local.y;
      const land = toWorld(slot.local.x + (r1 - 0.5) * 2.5, 2.2 + 2.2 + r2 * 4.5);
      const drift = side.clone().multiplyScalar(0.1 + 0.08 * r1).add(new Vector3(-0.05 + 0.1 * r2, 0, 0.02));
      return { slot, start, land, drift, spin: (r1 - 0.5) * 6, mat: new MeshStandardMaterial({ color: slot.color, roughness: 0.8 }) };
    });
  }, [lay, slots, n]);

  const refs = useRef<(Mesh | null)[]>([]);
  const p = useMemo(() => new Vector3(), []);

  useFrame(() => {
    const t = vis.t;
    for (let j = 0; j < plan.length; j++) {
      const m = refs.current[j];
      if (!m) continue;
      const c = plan[j];
      const age = t - throwFrame(ship, j);
      m.visible = age >= 0;
      if (age < 0) continue;
      const size = c.slot.spec.size;
      if (age < FLIGHT_FRAMES) {
        const u = age / FLIGHT_FRAMES;
        p.copy(c.start).lerp(c.land, u);
        waveAt(p.x, p.z, vis.wave, _w);
        p.y = c.start.y * (1 - u) + (_w.h - size * 0.25) * u + Math.sin(Math.PI * u) * 3.2;
        m.position.copy(p);
        m.rotation.set(u * c.spin, u * c.spin * 0.6, u * 2.2);
      } else {
        const d = age - FLIGHT_FRAMES;
        p.copy(c.land).addScaledVector(c.drift, d);
        waveAt(p.x, p.z, vis.wave, _w);
        const bob = Math.sin(vis.elapsed * 2 + j) * 0.06;
        m.position.set(p.x, _w.h - size * 0.25 + bob, p.z);
        m.rotation.set(-Math.atan(_w.dhdz) * 0.9 + c.spin, c.spin * 0.6 + d * 0.004, Math.atan(_w.dhdx) * 0.9 + 2.2);
      }
    }
  });

  return (
    <>
      {plan.map((c, j) => (
        <mesh
          key={j}
          ref={(m) => {
            refs.current[j] = m;
          }}
          geometry={geo}
          material={c.mat}
          scale={c.slot.spec.size * 0.94}
          visible={false}
        />
      ))}
    </>
  );
}
