import * as Tone from "tone";
import { PriceMelody } from "./melody";
import { ambienceGains, clamp, marketIntensity } from "./mix";

// Owned by CX (branch lane/cx-audio). CC-W imports this interface and never edits this file.

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

const AMBIENCE = ["sea_calm", "sea_rough", "wind", "rain", "storm"] as const;
const MUSIC = ["music_calm", "music_tension", "music_storm"] as const;
const EFFECTS = ["thunder_1", "thunder_2", "thunder_3", "foghorn", "splash", "creak", "sinking", "bell"] as const;
const VOICES = ["voice_alarm", "voice_margin_call", "voice_all_clear"] as const;
const dbGain = (db: number): number => 10 ** (db / 20);

export function createAudioEngine(): AudioEngine {
  const players = new Map<string, Tone.Player>();
  const gains = new Map<string, Tone.Gain>();
  const nodes: Tone.ToneAudioNode[] = [];
  const timers = new Set<ReturnType<typeof setTimeout>>();
  let master: Tone.Gain;
  let ambience: Tone.Gain;
  let music: Tone.Gain;
  let filter: Tone.Filter;
  let melody: PriceMelody;
  let starting: Promise<void> | undefined;
  let ready = false;
  let disposed = false;
  let muted = false;
  let latest: AudioFrame | undefined;
  let intensity = 0;
  let lastUpdate: number | undefined;
  let lastCreak = -Infinity;
  let musicState: number | undefined;
  let activeVoice: Tone.Player | undefined;
  let voiceVersion = 0;

  function later(action: () => void, seconds: number): void {
    const timer = setTimeout(() => {
      timers.delete(timer);
      if (!disposed && ready) action();
    }, Math.max(0, seconds) * 1000);
    timers.add(timer);
  }

  function duck(speaking: boolean): void {
    music.gain.rampTo(speaking ? dbGain(-8) : 1, speaking ? 0.04 : 0.3);
    ambience.gain.rampTo(speaking ? dbGain(-4) : 1, speaking ? 0.04 : 0.3);
  }

  function play(id: string, gain = 1): number {
    const player = players.get(id);
    if (!player?.loaded) return 0;
    player.volume.value = 20 * Math.log10(Math.max(0.001, gain));
    if (player.state === "started") player.stop();
    player.start();
    return player.buffer.duration;
  }

  function speak(id: string): void {
    const player = players.get(id);
    if (!player?.loaded) return;
    // A new announcement replaces the old one; an old timer cannot release its ducking.
    const version = ++voiceVersion;
    activeVoice?.stop();
    activeVoice = player;
    duck(true);
    const duration = play(id);
    later(() => {
      if (version === voiceVersion) {
        activeVoice = undefined;
        duck(false);
      }
    }, duration);
  }

  function cue(effect: string, voice: string): void {
    const duration = play(effect);
    if (duration > 0) later(() => speak(voice), duration + 0.08);
    else speak(voice);
  }

  function update(frame: AudioFrame): void {
    latest = { ...frame };
    if (!ready || disposed) return;
    const now = Tone.now();
    const elapsed = lastUpdate === undefined ? 0 : Math.max(0, now - lastUpdate);
    lastUpdate = now;
    const target = marketIntensity(frame.risk, frame.volRatio, frame.state);
    // 95% of an intensity transition arrives in 0.5s, independent of render rate.
    intensity += (target - intensity) * (1 - Math.exp(-elapsed / (0.5 / 3)));
    for (const [id, gain] of Object.entries(ambienceGains(intensity))) {
      gains.get(id)?.gain.rampTo(gain, 0.05);
    }
    filter.frequency.rampTo(800 + 11200 * intensity, 0.05);
    if (musicState !== frame.state) {
      MUSIC.forEach((id, index) => gains.get(id)?.gain.rampTo(index === frame.state ? 1 : 0, 2));
      musicState = frame.state;
    }
    if (Math.abs(frame.heel) > 15 && now - lastCreak >= 4) {
      lastCreak = now;
      play("creak", 0.6);
    }
    melody.update(frame);
  }

  async function initialize(): Promise<void> {
    await Tone.start();
    if (disposed) return;
    master = new Tone.Gain(muted ? 0 : 0.7).toDestination();
    ambience = new Tone.Gain(1).connect(master);
    music = new Tone.Gain(1).connect(master);
    filter = new Tone.Filter(800, "lowpass").connect(music);
    // Headroom for the sum of five ambience loops and overlapping music beds.
    const ambienceLevel = new Tone.Gain(0.24).connect(ambience);
    const musicLevel = new Tone.Gain(0.3).connect(filter);
    const effectsLevel = new Tone.Gain(0.6).connect(master);
    const voiceLevel = new Tone.Gain(0.8).connect(master);
    nodes.push(master, ambience, music, filter, ambienceLevel, musicLevel, effectsLevel, voiceLevel);
    melody = new PriceMelody(filter);

    async function load(id: string, destination: Tone.ToneAudioNode, loop: boolean): Promise<void> {
      const gain = new Tone.Gain(loop ? 0 : 1).connect(destination);
      const player = new Tone.Player({ loop, fadeIn: loop ? 0.05 : 0.005, fadeOut: 0.05 }).connect(gain);
      gains.set(id, gain);
      nodes.push(gain, player);
      try {
        await player.load(`/audio/${id}.mp3`);
        // Trim encoder padding so generated 60s beds retain their shared downbeat.
        if (loop) player.loopEnd = Math.min(id.startsWith("music_") ? 60 : 20, player.buffer.duration);
        if (!disposed) players.set(id, player);
      } catch {
        // An ungenerated or unavailable asset must never interrupt the replay.
      }
    }
    await Promise.all([
      ...AMBIENCE.map(id => load(id, ambienceLevel, true)),
      ...MUSIC.map(id => load(id, musicLevel, true)),
      ...EFFECTS.map(id => load(id, effectsLevel, false)),
      ...VOICES.map(id => load(id, voiceLevel, false)),
    ]);
    if (disposed) return;
    // Mute may have changed while downloads were pending.
    master.gain.value = muted ? 0 : 0.7;
    // Music beds share a downbeat and stay running under their state crossfades.
    const downbeat = Tone.now() + 0.05;
    for (const id of [...AMBIENCE, ...MUSIC]) players.get(id)?.start(downbeat);
    gains.get("sea_calm")?.gain.rampTo(1, 0.25);
    ready = true;
    if (latest) update(latest);
  }

  return {
    start(): Promise<void> {
      if (disposed) return Promise.resolve();
      if (!starting) {
        starting = initialize().catch(error => {
          // A browser may reject an audio unlock; allow a subsequent user click to retry.
          starting = undefined;
          throw error;
        });
      }
      return starting;
    },
    update,
    trigger(event: AudioEvent): void {
      if (!ready || disposed) return;
      switch (event.type) {
        case "jump":
          play(`thunder_${1 + Math.floor(Math.random() * 3)}`, 0.25 + 0.75 * clamp(Number.isFinite(event.strength) ? event.strength : 0));
          break;
        case "alarm": cue("foghorn", "voice_alarm"); break;
        case "cut": play("splash"); break;
        case "margin_call": cue("sinking", "voice_margin_call"); break;
        case "all_clear": cue("bell", "voice_all_clear"); break;
        case "narrate": {
          // Existing interface supports named local voice clips; no arbitrary URLs or fetches.
          const clip = event.clip.replace(/\.mp3$/, "");
          if (VOICES.some(id => id === clip)) speak(clip);
          break;
        }
        case "watch": break; // The watch music bed follows update().
      }
    },
    setMuted(value: boolean): void {
      muted = value;
      if (ready && !disposed) master.gain.rampTo(value ? 0 : 0.7, 0.05);
    },
    dispose(): void {
      if (disposed) return;
      disposed = true;
      ready = false;
      timers.forEach(timer => clearTimeout(timer));
      timers.clear();
      melody?.dispose();
      nodes.forEach(node => node.dispose());
      players.clear();
      gains.clear();
    },
  };
}
