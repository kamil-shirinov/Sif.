import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { CatmullRomCurve3, Color, Mesh, MeshBasicMaterial, PointLight, TubeGeometry, Vector3 } from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
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

const BOLT_VARIANTS = 6;
const BOLT_HEIGHT = 230;
const _fwd = new Vector3();
const _up = new Vector3(0, 1, 0);

/**
 * Where the next bolt should strike, if something else decides (the storm cell): set by StormCell, read here.
 * `active` false: the bolt falls somewhere in front of the camera, as before.
 */
export const strikeZone = { active: false, x: 0, z: 0, radius: 60, top: BOLT_HEIGHT };

/** Lightning on frames where series.jump = 1 (announced by the replay driver). */
export function Lightning() {
  const camera = useThree((s) => s.camera);
  const light = useRef<PointLight>(null);
  const strike = useRef({ age: 99, strength: 1, which: 0 });
  const mat = useMemo(() => new MeshBasicMaterial({ color: new Color(16, 17, 24), toneMapped: false, fog: false, transparent: true }), []);
  // A fixed set of bolts built once (each: a jagged main channel and three branches, merged). A strike picks one,
  // moves, turns and stretches it: nothing is built or uploaded while playing, and the material compiles at load.
  const bolts = useMemo(() => {
    return Array.from({ length: BOLT_VARIANTS }, (_, v) => {
      let s = (v * 9301 + 49297) % 233280;
      const rand = () => {
        s = (s * 9301 + 49297) % 233280;
        return s / 233280;
      };
      const top = new Vector3((rand() - 0.5) * 60, BOLT_HEIGHT, (rand() - 0.5) * 60);
      const geo = mergeGeometries(boltGeometries(top, new Vector3(0, 0, 0), rand).map((g) => (g.index ? g.toNonIndexed() : g)))!;
      const m = new Mesh(geo, mat);
      m.visible = false;
      m.frustumCulled = false;
      return m;
    });
  }, [mat]);
  useEffect(
    () => () => {
      bolts.forEach((b) => b.geometry.dispose());
      mat.dispose();
    },
    [bolts, mat],
  );

  useEffect(
    () =>
      onJump(({ frame, strength }) => {
        let s = (frame * 9301 + 49297) % 233280;
        const rand = () => {
          s = (s * 9301 + 49297) % 233280;
          return s / 233280;
        };
        const which = frame % BOLT_VARIANTS;
        const b = bolts[which];
        let height = BOLT_HEIGHT;
        if (strikeZone.active) {
          // Inside the storm cell: under its base, anywhere within its rain.
          const a = rand() * Math.PI * 2;
          const r = Math.sqrt(rand()) * strikeZone.radius;
          b.position.set(strikeZone.x + Math.cos(a) * r, 0, strikeZone.z + Math.sin(a) * r);
          height = strikeZone.top;
        } else {
          // Somewhere in front of the camera, out over the sea.
          camera.getWorldDirection(_fwd);
          _fwd.y = 0;
          _fwd.normalize().applyAxisAngle(_up, (rand() - 0.5) * 1.6);
          b.position.set(camera.position.x, 0, camera.position.z).addScaledVector(_fwd, 160 + rand() * 260);
        }
        b.rotation.y = rand() * Math.PI * 2;
        b.scale.set(1, height / BOLT_HEIGHT, 1);
        if (light.current) light.current.position.set(b.position.x, height * 0.6, b.position.z);
        vis.flashPos.set(b.position.x, height, b.position.z);
        strike.current.age = 0;
        strike.current.strength = strength;
        strike.current.which = which;
      }),
    [camera, bolts],
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
    for (let i = 0; i < bolts.length; i++) bolts[i].visible = i === st.which && k > 0.02;
    if (light.current) light.current.intensity = k * 60000;
  });

  return (
    <>
      {bolts.map((b, i) => (
        <primitive key={i} object={b} />
      ))}
      <pointLight ref={light} intensity={0} distance={900} decay={1.6} color="#cfdcff" />
    </>
  );
}
