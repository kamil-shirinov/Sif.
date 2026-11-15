import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Spherical, Vector3 } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { waveAt, type WaveSample } from "./waves";
import { vis } from "./vis";
import { cameraDirector, easeInOutCubic, placeCamera } from "./cameraDirector";
import { useApp } from "../state/app";

export const HOME_POS = new Vector3(4, 8.5, 38);
export const HOME_TARGET = new Vector3(0, 2.2, 0);
/**
 * The landing page's wide shot: further back and higher, aimed left of the ships so they sail in the open right-hand
 * part of the screen while the text sits over the dark left. It sways slowly (LANDING_SWAY) instead of orbiting, so the
 * ships never drift under the text.
 */
export const LANDING_POS = new Vector3(-18, 13, 50);
export const LANDING_TARGET = new Vector3(-24, 5.5, -6);
const LANDING_SWAY = { azimuth: 0.075, elevation: 0.025, periodS: 46 };
const IDLE_S = 5;
const MIN_CLEARANCE = 1.6; // camera stays this far above the wave surface
const MIN_DISTANCE = 8;
const MAX_DISTANCE = 320;
const _surf: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };

/**
 * ?cam=<azimuth>,<elevation>[,<distance>]: start the camera there (degrees around the ships, 0 = the home
 * side; degrees above the sea; scene units) and keep it there until the first drag, like ?at= for frames.
 * For screenshots and for checking the sky from every side.
 */
function cameraFromUrl(): Vector3 | null {
  try {
    const raw = new URLSearchParams(window.location.search).get("cam");
    if (!raw) return null;
    const [az, el, dist] = raw.split(",").map(Number);
    if (!Number.isFinite(az) || !Number.isFinite(el)) return null;
    const radius = Number.isFinite(dist) ? Math.min(MAX_DISTANCE, Math.max(MIN_DISTANCE, dist)) : HOME_POS.distanceTo(HOME_TARGET);
    const phi = Math.PI / 2 - (Math.min(87, Math.max(0, el)) * Math.PI) / 180;
    return new Vector3().setFromSpherical(new Spherical(radius, phi, (az * Math.PI) / 180)).add(HOME_TARGET);
  } catch {
    return null;
  }
}

/**
 * Drag to orbit 360 degrees, look down from above, scroll to zoom.
 * After 5 s idle the camera drifts back into a slow cinematic orbit. Double-click resets.
 */
export function CameraRig() {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera, gl } = useThree();
  const urlCam = useMemo(cameraFromUrl, []);
  // With ?cam= the camera is never "idle" until the first drag, so it stays where it was put.
  const st = useRef({ lastInput: urlCam ? Infinity : -Infinity, interacting: false, resetUntil: 0 });
  const sph = useMemo(() => new Spherical(), []);
  const home = useMemo(() => new Spherical().setFromVector3(HOME_POS.clone().sub(HOME_TARGET)), []);
  const off = useMemo(() => new Vector3(), []);
  const landingSph = useMemo(() => new Spherical().setFromVector3(LANDING_POS.clone().sub(LANDING_TARGET)), []);
  // A flight in progress: where it took off from (target and spherical offset), the eased fraction it is at.
  const fl = useMemo(() => ({ active: false, fromTarget: new Vector3(), fromSph: new Spherical(), toTarget: new Vector3(), toSph: new Spherical() }), []);
  const swayT0 = useMemo(() => performance.now(), []);

  useEffect(() => {
    // The landing page opens on its wide shot (unless ?cam= put the camera somewhere on purpose).
    const startOnLanding = useApp.getState().landing && !urlCam;
    placeCamera(startOnLanding ? "landing" : "home");
    camera.position.copy(urlCam ?? (startOnLanding ? LANDING_POS : HOME_POS));
    camera.lookAt(startOnLanding ? LANDING_TARGET : HOME_TARGET);
    const el = gl.domElement;
    const onDbl = () => {
      st.current.resetUntil = performance.now() + 1400;
      st.current.lastInput = -Infinity;
    };
    el.addEventListener("dblclick", onDbl);
    return () => el.removeEventListener("dblclick", onDbl);
  }, [camera, gl, urlCam]);

  useEffect(() => {
    const c = controls.current;
    if (!c) return;
    c.target.copy(cameraDirector.view === "landing" && !urlCam ? LANDING_TARGET : HOME_TARGET);
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

  /** The landing's wide shot at time `now`, with its slow sway, as a target and a spherical offset. */
  const landingAt = (now: number, target: Vector3, out: Spherical) => {
    const ph = (((now - swayT0) / 1000) * Math.PI * 2) / LANDING_SWAY.periodS;
    target.copy(LANDING_TARGET);
    out.copy(landingSph);
    out.theta += Math.sin(ph) * LANDING_SWAY.azimuth;
    out.phi += Math.sin(ph * 0.71 + 1.3) * LANDING_SWAY.elevation;
  };

  useFrame((_, dt) => {
    const c = controls.current;
    if (!c) return;
    const now = performance.now();
    const s = st.current;
    const dir = cameraDirector;

    // A flight between the landing's wide shot and the replay's view: eased (cubic in-out) over its duration, on an
    // arc (the offset from the target is interpolated in spherical coordinates, the target in a straight line).
    if (dir.flight) {
      const f = dir.flight;
      if (!fl.active) {
        fl.active = true;
        fl.fromTarget.copy(c.target);
        fl.fromSph.setFromVector3(off.copy(camera.position).sub(c.target));
      }
      if (f.to === "landing") landingAt(now + Math.max(0, f.start + f.duration - now), fl.toTarget, fl.toSph);
      else {
        fl.toTarget.copy(HOME_TARGET);
        fl.toSph.copy(home);
      }
      const u = Math.min(1, (now - f.start) / f.duration);
      const e = easeInOutCubic(u);
      c.target.lerpVectors(fl.fromTarget, fl.toTarget, e);
      let dTheta = fl.toSph.theta - fl.fromSph.theta;
      dTheta = Math.atan2(Math.sin(dTheta), Math.cos(dTheta));
      sph.set(
        fl.fromSph.radius + (fl.toSph.radius - fl.fromSph.radius) * e,
        fl.fromSph.phi + (fl.toSph.phi - fl.fromSph.phi) * e,
        fl.fromSph.theta + dTheta * e,
      );
      camera.position.copy(c.target).add(off.setFromSpherical(sph));
      camera.lookAt(c.target);
      c.enabled = false;
      c.autoRotate = false;
      if (u >= 1) {
        fl.active = false;
        dir.flight = null;
        // Settled on the replay's view: the idle drift waits its usual 5 s before it starts.
        s.lastInput = now;
        s.resetUntil = 0;
        f.done();
      }
    } else if (dir.view === "landing" && !urlCam) {
      // The landing page: hold the wide shot, swaying slowly. No dragging under the page.
      fl.active = false;
      landingAt(now, c.target, sph);
      camera.position.copy(c.target).add(off.setFromSpherical(sph));
      camera.lookAt(c.target);
      c.enabled = false;
      c.autoRotate = false;
    }
    if (dir.flight || (dir.view === "landing" && !urlCam)) {
      const surface = waveAt(camera.position.x, camera.position.z, vis.wave, _surf).h;
      if (camera.position.y < surface + MIN_CLEARANCE) camera.position.y = surface + MIN_CLEARANCE;
      return;
    }
    c.enabled = true;
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
    const surface = waveAt(camera.position.x, camera.position.z, vis.wave, _surf).h;
    if (camera.position.y < surface + MIN_CLEARANCE) camera.position.y = surface + MIN_CLEARANCE;
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={MIN_DISTANCE}
      maxDistance={MAX_DISTANCE}
      minPolarAngle={0}
      maxPolarAngle={Math.PI / 2 - 0.03}
      enablePan
      panSpeed={0.6}
      rotateSpeed={0.6}
    />
  );
}
