// Tiny event bus: the replay driver announces frame crossings; the scene reacts.
// Only events the replay crosses while playing are announced (a seek announces nothing).
export interface JumpPayload {
  frame: number;
  strength: number;
}

type Handler = (p: JumpPayload) => void;
const jumpHandlers = new Set<Handler>();

export function onJump(h: Handler): () => void {
  jumpHandlers.add(h);
  return () => {
    jumpHandlers.delete(h);
  };
}

export function emitJump(p: JumpPayload) {
  jumpHandlers.forEach((h) => h(p));
}

/** A bundle event (watch, squall, alarm, fair_wind, cut, restore, margin_call, all_clear) was crossed. */
export interface SceneEventPayload {
  type: string;
  frame: number;
}

type SceneHandler = (p: SceneEventPayload) => void;
const sceneHandlers = new Set<SceneHandler>();

export function onSceneEvent(h: SceneHandler): () => void {
  sceneHandlers.add(h);
  return () => {
    sceneHandlers.delete(h);
  };
}

export function emitSceneEvent(p: SceneEventPayload) {
  sceneHandlers.forEach((h) => h(p));
}
