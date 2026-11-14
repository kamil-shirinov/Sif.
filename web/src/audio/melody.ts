import * as Tone from "tone";
import type { AudioFrame } from "./engine";
import { clamp } from "./mix";

// C minor pentatonic, C3 through C5 inclusive (two octaves).
const MIDI_NOTES = [48, 51, 53, 55, 58, 60, 63, 65, 67, 70, 72];

export class PriceMelody {
  private readonly synth: Tone.Synth;
  private minute: number | undefined;
  private reference = 0;
  private previousPrice = 0;
  private previousNote = 5;
  private readonly timers = new Set<ReturnType<typeof setTimeout>>();

  constructor(destination: Tone.ToneAudioNode) {
    this.synth = new Tone.Synth({
      oscillator: { type: "sine" },
      envelope: { attack: 0.015, decay: 0.2, sustain: 0.08, release: 0.7 },
      volume: -18,
    }).connect(destination);
  }

  update(frame: AudioFrame): void {
    if (!Number.isInteger(frame.minuteIndex) || !(frame.price > 0) || !Number.isFinite(frame.price)) return;
    if (this.minute === frame.minuteIndex) return;
    const rewound = this.minute !== undefined && frame.minuteIndex < this.minute;
    if (this.reference === 0 || rewound) {
      this.reference = frame.price;
      this.previousPrice = frame.price;
      this.previousNote = 5;
      this.synth.triggerRelease();
    }
    this.timers.forEach(timer => clearTimeout(timer));
    this.timers.clear();
    this.minute = frame.minuteIndex;
    // A fixed reference per replay keeps pitch monotonic with price; +/-1% spans two octaves.
    const position = clamp(0.5 + Math.log(frame.price / this.reference) / 0.02);
    const note = Math.round(position * (MIDI_NOTES.length - 1));
    const move = Math.log(frame.price / this.previousPrice);
    const velocity = clamp(0.12 + Math.abs(move) * 90, 0.12, 0.55);
    const previousNote = this.previousNote;
    this.previousPrice = frame.price;
    this.previousNote = note;
    if (frame.state === 0 && frame.minuteIndex % 4 !== 0) return;

    const now = Tone.now() + 0.02;
    // One ordinary note per minute; a sharp downward move becomes a short descending run.
    // Emit run notes just in time, so a new minute can cancel remaining steps.
    if (move <= -0.003 && note < previousNote) {
      const start = Math.min(MIDI_NOTES.length - 1, Math.max(previousNote, note + 3));
      const steps = Math.min(5, start - note + 1);
      for (let step = 0; step < steps; step += 1) {
        const index = Math.round(start + (note - start) * step / (steps - 1));
        const play = (): void => {
          this.synth.triggerAttackRelease(Tone.Frequency(MIDI_NOTES[index], "midi").toFrequency(),
            0.055, Tone.now() + 0.02, velocity * (1 - step * 0.07));
        };
        if (step === 0) play();
        else {
          const timer = setTimeout(() => {
            this.timers.delete(timer);
            play();
          }, step * 90);
          this.timers.add(timer);
        }
      }
    } else {
      this.synth.triggerAttackRelease(Tone.Frequency(MIDI_NOTES[note], "midi").toFrequency(), 0.18, now, velocity);
    }
  }

  dispose(): void {
    this.timers.forEach(timer => clearTimeout(timer));
    this.timers.clear();
    this.synth.dispose();
  }
}
