import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Spherical, Vector3 } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { waveAt } from "./waves";
import { vis } from "./vis";

export const HOME_POS = new Vector3(4, 8.5, 38);
export const HOME_TARGET = new Vector3(0, 2.2, 0);
const IDLE_S = 5;
const MIN_CLEARANCE = 1.6; // camera stays this far above the wave surface

/**
 * Drag to orbit 360 degrees, look down from above, scroll to zoom.
 * After 5 s idle the camera drifts back into a slow cinematic orbit. Double-click resets.
 */
export function CameraRig() {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera, gl } = useThree();
  const st = useRef({ lastInput: -Infinity, interacting: false, resetUntil: 0 });
  const sph = useMemo(() => new Spherical(), []);
  const home = useMemo(() => new Spherical().setFromVector3(HOME_POS.clone().sub(HOME_TARGET)), []);
  const off = useMemo(() => new Vector3(), []);

  useEffect(() => {
    camera.position.copy(HOME_POS);
    camera.lookAt(HOME_TARGET);
    const el = gl.domElement;
    const onDbl = () => {
      st.current.resetUntil = performance.now() + 1400;
      st.current.lastInput = -Infinity;
    };
    el.addEventListener("dblclick", onDbl);
    return () => el.removeEventListener("dblclick", onDbl);
  }, [camera, gl]);

  useEffect(() => {
    const c = controls.current;
    if (!c) return;
    c.target.copy(HOME_TARGET);
    c.update();
    const start = () => {
      st.current.interacting = true;
      st.current.lastInput = performance.now();
      st.current.resetUntil = 0;
    };
    const end = () => {
      st.current.interacting = false;
      st.current.lastInput = performance.now();
    };
    c.addEventListener("start", start);
    c.addEventListener("end", end);
    return () => {
      c.removeEventListener("start", start);
      c.removeEventListener("end", end);
    };
  }, []);

  useFrame((_, dt) => {
    const c = controls.current;
    if (!c) return;
    const now = performance.now();
    const s = st.current;
    const resetting = now < s.resetUntil;
    const idle = !s.interacting && (now - s.lastInput) / 1000 > IDLE_S;
    c.autoRotate = idle && !resetting;
    c.autoRotateSpeed = 0.28;
    if (idle || resetting) {
      const k = 1 - Math.exp(-dt * (resetting ? 4 : 0.35));
      c.target.lerp(HOME_TARGET, k);
      off.copy(camera.position).sub(c.target);
      sph.setFromVector3(off);
      sph.radius += (home.radius - sph.radius) * k;
      sph.phi += (home.phi - sph.phi) * k;
      if (resetting) {
        let dTheta = home.theta - sph.theta;
        dTheta = Math.atan2(Math.sin(dTheta), Math.cos(dTheta));
        sph.theta += dTheta * k;
      }
      off.setFromSpherical(sph);
      camera.position.copy(c.target).add(off);
    }
    // Keep the camera above the waterline (waves included).
    const surface = waveAt(camera.position.x, camera.position.z, vis.wave).h;
    if (camera.position.y < surface + MIN_CLEARANCE) camera.position.y = surface + MIN_CLEARANCE;
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={8}
      maxDistance={320}
      minPolarAngle={0}
      maxPolarAngle={Math.PI / 2 - 0.03}
      enablePan
      panSpeed={0.6}
      rotateSpeed={0.6}
    />
  );
}
