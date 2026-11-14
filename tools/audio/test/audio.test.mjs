import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

// Execute the actual TypeScript modules against a deterministic offline Tone surface.
// Type checking separately verifies these calls against the real installed Tone types.
const urls = new Map();
for (const name of ['mix', 'melody', 'engine']) {
  let js = ts.transpileModule(await readFile(new URL(`../../../web/src/audio/${name}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText;
  js = js.replace('import * as Tone from "tone";', 'const Tone = globalThis.__audioTestTone;');
  for (const [module, url] of urls) js = js.replaceAll(`"./${module}"`, JSON.stringify(url));
  urls.set(name, `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
}
let clock = 0;
let nodes = [];
let missing = new Set();
let unlocks = 0;
class Param {
  constructor(value = 0) { this.value = value; this.ramps = []; }
  rampTo(value, seconds) { this.value = value; this.ramps.push([value, seconds]); }
}
class Node {
  constructor() { nodes.push(this); this.outputs = []; }
  connect(destination) { this.outputs.push(destination); return this; }
  toDestination() { return this; }
  dispose() { this.disposed = true; }
}
class Gain extends Node { constructor(value) { super(); this.gain = new Param(value); } }
class Filter extends Node { constructor(value) { super(); this.frequency = new Param(value); } }
class Player extends Node {
  constructor(options) { super(); this.options = options; this.volume = new Param(); this.buffer = { duration: 1 }; this.starts = []; this.state = 'stopped'; }
  async load(url) { this.id = url.split('/').at(-1).replace('.mp3', ''); if (missing.has(this.id)) throw Error('missing'); this.loaded = true; return this; }
  start(time) { this.starts.push({ time, volume: this.volume.value }); this.state = 'started'; return this; }
  stop() { this.state = 'stopped'; return this; }
}
class Synth extends Node {
  constructor(options) { super(); this.options = options; this.notes = []; }
  triggerAttackRelease(...args) { this.notes.push(args); }
  triggerRelease() {}
}
globalThis.__audioTestTone = {
  Gain, Filter, Player, Synth, now: () => clock,
  start: async () => { unlocks++; },
  Frequency: (midi) => ({ toFrequency: () => midi }),
};
const { createAudioEngine } = await import(urls.get('engine'));
const { PriceMelody } = await import(urls.get('melody'));
const { marketIntensity, ambienceGains } = await import(urls.get('mix'));
const frame = (extra = {}) => ({ risk: 0, volRatio: 1, state: 0, heel: 0, price: 100, minuteIndex: 0, ...extra });
const player = id => nodes.find(node => node instanceof Player && node.id === id);
const reset = () => { clock = 0; nodes = []; missing = new Set(); unlocks = 0; };

await test('market audio behaviour offline', async t => {
  await t.test('intensity follows the specified formula and layered thresholds', () => {
    assert.equal(marketIntensity(1, 9, 2), 1);
    assert.equal(marketIntensity(0.6, 5, 1), 0.44999999999999996);
    assert.equal(marketIntensity(0, 0, 0), 0);
    assert.equal(marketIntensity(100, 100, 2), 1);
    assert.deepEqual(ambienceGains(0), { sea_calm: 1, sea_rough: 0, wind: 0, rain: 0, storm: 0 });
    assert.deepEqual(ambienceGains(1), { sea_calm: 0, sea_rough: 1, wind: 1, rain: 1, storm: 1 });
    assert.equal(ambienceGains(0.35).rain, 0);
  });

  await t.test('start is idempotent, shares music downbeat, and preserves pre-start mute', async () => {
    reset();
    const engine = createAudioEngine();
    engine.setMuted(true);
    engine.update(frame({ state: 2 }));
    await Promise.all([engine.start(), engine.start()]);
    assert.equal(unlocks, 1);
    assert.equal(nodes.filter(n => n instanceof Player).length, 19);
    assert.equal(nodes.find(n => n instanceof Gain).gain.value, 0);
    assert.equal(player('music_calm').starts[0].time, player('music_storm').starts[0].time);
    assert.deepEqual(player('music_storm').outputs[0].gain.ramps.at(-1), [1, 2]);
    engine.dispose();
    assert.ok(nodes.every(n => n.disposed));
  });

  await t.test('mute changes during loading take effect before loops start', async () => {
    reset(); const engine = createAudioEngine();
    const pending = engine.start();
    await Promise.resolve(); // initialize() has created the graph and started loads
    engine.setMuted(true);
    await pending;
    assert.equal(nodes.find(n => n instanceof Gain).gain.value, 0);
    engine.dispose();
  });

  await t.test('intensity smooths over half a second and opens the filter', async () => {
    reset();
    const engine = createAudioEngine(); await engine.start();
    engine.update(frame());
    clock = 0.5;
    engine.update(frame({ risk: 1, volRatio: 9, state: 2, minuteIndex: 1 }));
    const rough = player('sea_rough').outputs[0].gain.value;
    assert.ok(Math.abs(rough - (1 - Math.exp(-3))) < 1e-10);
    assert.ok(Math.abs(nodes.find(n => n instanceof Filter).frequency.value - (800 + 11200 * rough)) < 1e-8);
    engine.dispose();
  });

  await t.test('creak is rate limited and signed heel works', async () => {
    reset(); const engine = createAudioEngine(); await engine.start();
    engine.update(frame({ heel: -16 }));
    clock = 3.9; engine.update(frame({ heel: 25 }));
    assert.equal(player('creak').starts.length, 1);
    clock = 4; engine.update(frame({ heel: 16 }));
    assert.equal(player('creak').starts.length, 2);
    engine.dispose();
  });

  await t.test('alarm waits for foghorn, ducks buses during speech, then restores them', async context => {
    reset(); context.mock.timers.enable({ apis: ['setTimeout'] });
    const engine = createAudioEngine(); await engine.start();
    const music = nodes.find(n => n instanceof Filter).outputs[0];
    const ambience = player('sea_calm').outputs[0].outputs[0].outputs[0];
    engine.trigger({ type: 'alarm' });
    assert.equal(player('foghorn').starts.length, 1);
    assert.equal(player('voice_alarm').starts.length, 0);
    context.mock.timers.tick(1081);
    assert.equal(player('voice_alarm').starts.length, 1);
    assert.ok(Math.abs(music.gain.value - 10 ** (-8 / 20)) < 1e-12);
    assert.ok(Math.abs(ambience.gain.value - 10 ** (-4 / 20)) < 1e-12);
    context.mock.timers.tick(1001);
    assert.equal(music.gain.value, 1); assert.equal(ambience.gain.value, 1);
    engine.dispose(); context.mock.timers.reset();
  });

  await t.test('missing files remain silent and do not block voice-only cues', async () => {
    reset(); missing = new Set(['sea_calm', 'foghorn', 'thunder_1', 'thunder_2', 'thunder_3']);
    const engine = createAudioEngine(); await engine.start();
    engine.update(frame());
    engine.trigger({ type: 'alarm' });
    engine.trigger({ type: 'jump', strength: 1 });
    assert.equal(player('voice_alarm').starts.length, 1);
    assert.equal(player('sea_calm').starts.length, 0);
    engine.dispose();
  });

  await t.test('all event effects map correctly and disposal cancels pending speech', async context => {
    reset(); context.mock.timers.enable({ apis: ['setTimeout'] });
    const engine = createAudioEngine(); await engine.start();
    engine.trigger({ type: 'cut' });
    engine.trigger({ type: 'margin_call' });
    engine.trigger({ type: 'all_clear' });
    for (const id of ['splash', 'sinking', 'bell']) assert.equal(player(id).starts.length, 1);
    engine.dispose(); context.mock.timers.tick(5000);
    for (const id of ['voice_margin_call', 'voice_all_clear']) assert.equal(player(id).starts.length, 0);
    context.mock.timers.reset();
  });

  await t.test('jump strength controls thunder loudness', async () => {
    reset(); const engine = createAudioEngine(); await engine.start();
    engine.trigger({ type: 'jump', strength: 0 });
    engine.trigger({ type: 'jump', strength: 1 });
    const volumes = nodes.filter(n => n instanceof Player && n.id.startsWith('thunder_'))
      .flatMap(n => n.starts.map(start => start.volume)).sort((a, b) => a - b);
    assert.ok(Math.abs(volumes[0] - 20 * Math.log10(0.25)) < 1e-10);
    assert.equal(volumes[1], 0);
    engine.dispose();
  });

  await t.test('replacement voice keeps ducking until the new voice ends', async context => {
    reset(); context.mock.timers.enable({ apis: ['setTimeout'] });
    const engine = createAudioEngine(); await engine.start();
    const music = nodes.find(n => n instanceof Filter).outputs[0];
    engine.trigger({ type: 'narrate', clip: 'voice_alarm.mp3' });
    context.mock.timers.tick(500);
    engine.trigger({ type: 'narrate', clip: 'voice_margin_call' });
    context.mock.timers.tick(501);
    assert.ok(music.gain.value < 1);
    context.mock.timers.tick(500);
    assert.equal(music.gain.value, 1);
    engine.dispose(); context.mock.timers.reset();
  });

  await t.test('disposal while unlocking audio prevents late initialization', async () => {
    reset(); const engine = createAudioEngine();
    const pending = engine.start(); engine.dispose(); await pending;
    assert.equal(nodes.length, 0);
    await engine.start(); assert.equal(unlocks, 1);
  });

  await t.test('melody is sparse in calm, deduplicates minutes, and rises with price', () => {
    reset(); const melody = new PriceMelody(new Gain(1));
    const synth = nodes.find(n => n instanceof Synth);
    melody.update(frame()); melody.update(frame());
    melody.update(frame({ minuteIndex: 1, price: 100.1 }));
    assert.equal(synth.notes.length, 1);
    melody.update(frame({ minuteIndex: 4, price: 100.5 }));
    assert.equal(synth.notes.length, 2);
    assert.ok(synth.notes[1][0] > synth.notes[0][0]);
    assert.ok(synth.notes[1][3] > synth.notes[0][3]);
    melody.dispose();
  });

  await t.test('crash plays a falling pentatonic run and rewind resets its price reference', context => {
    reset(); context.mock.timers.enable({ apis: ['setTimeout'] });
    const melody = new PriceMelody(new Gain(1));
    const synth = nodes.find(n => n instanceof Synth);
    melody.update(frame({ state: 2 }));
    melody.update(frame({ state: 2, minuteIndex: 1, price: 99.2 }));
    for (let i = 0; i < 5; i++) { clock += 0.09; context.mock.timers.tick(90); }
    const run = synth.notes.slice(1).map(note => note[0]);
    assert.ok(run.length >= 3);
    assert.ok(run.every((note, i) => i === 0 || note < run[i - 1]));
    melody.update(frame({ state: 2, price: 150 }));
    assert.equal(synth.notes.at(-1)[0], 60);
    melody.dispose(); context.mock.timers.reset();
  });
});
