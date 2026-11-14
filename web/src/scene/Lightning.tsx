import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { CatmullRomCurve3, Color, Group, Mesh, MeshBasicMaterial, PointLight, TubeGeometry, Vector3 } from "three";
import { onJump } from "../lib/bus";
import { vis } from "./vis";

/** Jagged bolt from cloud base to the sea, with a couple of branches. */
function boltGeometries(start: Vector3, end: Vector3, rand: () => number): TubeGeometry[] {
  const make = (a: Vector3, b: Vector3, segs: number, jitter: number, radius: number) => {
    const pts: Vector3[] = [];
    for (let i = 0; i <= segs; i++) {
      const p = a.clone().lerp(b, i / segs);
      if (i > 0 && i < segs) p.add(new Vector3((rand() - 0.5) * jitter, (rand() - 0.5) * jitter * 0.3, (rand() - 0.5) * jitter));
      pts.push(p);
    }
    return { geo: new TubeGeometry(new CatmullRomCurve3(pts, false, "catmullrom", 0.1), segs * 3, radius, 4, false), pts };
  };
  const main = make(start, end, 14, 26, 0.9);
  const out = [main.geo];
  for (let k = 0; k < 3; k++) {
    const from = main.pts[3 + Math.floor(rand() * 8)];
    const to = from.clone().add(new Vector3((rand() - 0.5) * 70, -30 - rand() * 50, (rand() - 0.5) * 70));
    out.push(make(from, to, 6, 14, 0.45).geo);
  }
  return out;
}

/** Lightning on frames where series.jump = 1 (announced by the replay driver). */
export function Lightning() {
  const camera = useThree((s) => s.camera);
  const group = useRef<Group>(null);
  const light = useRef<PointLight>(null);
  const strike = useRef({ age: 99, strength: 1, seq: 0 });
  const mat = useMemo(() => new MeshBasicMaterial({ color: new Color(16, 17, 24), toneMapped: false, fog: false, transparent: true }), []);

  useEffect(
    () =>
      onJump(({ frame, strength }) => {
        const g = group.current;
        if (!g) return;
        let s = (frame * 9301 + 49297) % 233280;
        const rand = () => {
          s = (s * 9301 + 49297) % 233280;
          return s / 233280;
        };
        // Strike somewhere in front of the camera, out over the sea.
        const fwd = new Vector3();
        camera.getWorldDirection(fwd);
        fwd.y = 0;
        fwd.normalize();
        const ang = (rand() - 0.5) * 1.6;
        const dist = 160 + rand() * 260;
        const dir = fwd.applyAxisAngle(new Vector3(0, 1, 0), ang);
        const ground = new Vector3(camera.position.x, 0, camera.position.z).addScaledVector(dir, dist);
        const top = ground.clone().add(new Vector3((rand() - 0.5) * 60, 230, (rand() - 0.5) * 60));
        for (const c of [...g.children]) {
          const m = c as Mesh;
          m.geometry.dispose();
          g.remove(m);
        }
        for (const geo of boltGeometries(top, ground, rand)) g.add(new Mesh(geo, mat));
        if (light.current) light.current.position.copy(top).lerp(ground, 0.4);
        vis.flashPos.copy(top);
        strike.current = { age: 0, strength, seq: strike.current.seq + 1 };
      }),
    [camera, mat],
  );

  useFrame((_, dt) => {
    const st = strike.current;
    st.age += Math.min(dt, 0.05); // slow frames still show every strike for a few frames
    const a = st.age;
    // Two quick pulses then decay.
    const pulse = a < 0.06 ? 1 : a < 0.11 ? 0.25 : a < 0.17 ? 0.9 : Math.max(0, 0.9 - (a - 0.17) * 3.2);
    const k = pulse * (0.6 + 0.4 * st.strength);
    vis.flash = Math.max(vis.flash, k * 0.9);
    mat.opacity = Math.min(1, k * 1.4);
    if (group.current) group.current.visible = k > 0.02;
    if (light.current) light.current.intensity = k * 60000;
  });

  return (
    <>
      <group ref={group} />
      <pointLight ref={light} intensity={0} distance={900} decay={1.6} color="#cfdcff" />
    </>
  );
}
