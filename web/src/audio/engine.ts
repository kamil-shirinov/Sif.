// Owned by CX (branch lane/cx-audio). CC-W imports this interface and never edits this file.
// This stub does nothing, so the web app builds before the real engine lands.

export type AudioFrame = {
  risk: number; // 0 to 1
  volRatio: number; // 1 = normal volatility
  state: 0 | 1 | 2; // calm, watch, storm
  heel: number; // ship tilt in degrees, signed
  price: number; // current mid price, for the price melody
  minuteIndex: number; // frame index, so the melody plays one note per market minute
};

export type AudioEvent =
  | { type: "jump"; strength: number }
  | { type: "watch" }
  | { type: "alarm" }
  | { type: "cut" }
  | { type: "margin_call" }
  | { type: "all_clear" }
  | { type: "narrate"; clip: string };

export interface AudioEngine {
  start(): Promise<void>; // call from a user click: browsers block sound before one
  update(frame: AudioFrame): void; // call every animation frame
  trigger(event: AudioEvent): void; // call when an event fires
  setMuted(muted: boolean): void;
  dispose(): void;
}

export function createAudioEngine(): AudioEngine {
  return {
    async start() {},
    update() {},
    trigger() {},
    setMuted() {},
    dispose() {},
  };
}
