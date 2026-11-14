// Tiny event bus: the replay driver announces frame crossings; the scene reacts (lightning).
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
