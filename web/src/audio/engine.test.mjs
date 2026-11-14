import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import test from 'node:test';

// Keep the regression in the audio lane, using its existing isolated dependencies.
const require = createRequire(new URL('../../../tools/audio/package.json', import.meta.url));
const ts = require('typescript');
const modules = new Map();
for (const name of ['mix', 'melody', 'engine']) {
  let js = ts.transpileModule(await readFile(new URL(`./${name}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText;
  js = js.replace('import * as Tone from "tone";', 'const Tone = globalThis.__retriggerTestTone;');
  for (const [name, url] of modules) js = js.replaceAll(`"./${name}"`, JSON.stringify(url));
  modules.set(name, `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
}

let clock;
let nodes;
class Param {
  constructor(value) { this.value = value; }
  rampTo(value) { this.value = value; }
}
class Node {
  constructor() { nodes.push(this); }
  connect(destination) { this.destination = destination; return this; }
  toDestination() { return this; }
  dispose() { this.disposed = true; }
}
class Gain extends Node { constructor(value) { super(); this.gain = new Param(value); } }
class Filter extends Node { constructor(value) { super(); this.frequency = new Param(value); } }
class Player extends Node {
  constructor() {
    super(); this.volume = new Param(0); this.buffer = { duration: 1 }; this.starts = []; this.stops = [];
  }
  async load(url) { this.id = url.split('/').at(-1).replace('.mp3', ''); this.loaded = true; }
  get state() { return this.starts.at(-1) <= clock ? 'started' : 'stopped'; }
  start(time = clock) {
    if (time <= this.starts.at(-1)) throw Error('Start time must be strictly greater than previous start time');
    this.starts.push(time);
  }
  stop(time = clock) { this.stops.push(time); }
}
class Synth extends Node {
  triggerAttackRelease() {}
  triggerRelease() {}
}
const tone = globalThis.__retriggerTestTone = {
  Gain, Filter, Player, Synth, now: () => clock, start: async () => {},
  Frequency: midi => ({ toFrequency: () => midi }),
};
const { createAudioEngine } = await import(modules.get('engine'));
const player = id => nodes.find(node => node instanceof Player && node.id === id);
const frame = { risk: 1, volRatio: 9, state: 2, heel: 0, price: 100, minuteIndex: 0 };
const fail = () => { throw Error('audio unavailable'); };

await test('audio retriggers and failure isolation', async t => {
  t.beforeEach(() => { clock = 10; nodes = []; });

  await t.test('same-tick cuts, thunder and voices always start strictly later', async context => {
    context.mock.timers.enable({ apis: ['setTimeout'] });
    context.mock.method(Math, 'random', () => 0);
    const engine = createAudioEngine(); await engine.start();
    try {
      for (const [event, id] of [
        [{ type: 'cut' }, 'splash'],
        [{ type: 'jump', strength: 1 }, 'thunder_1'],
        [{ type: 'narrate', clip: 'voice_alarm' }, 'voice_alarm'],
      ]) {
        assert.doesNotThrow(() => {
          engine.trigger(event);
          engine.trigger(event); // Same tick: no clock advance between calls.
          for (let i = 0; i < 8; i++) engine.trigger(event);
        });
        const starts = player(id).starts;
        assert.equal(starts.length, 10); // Swallowing a scheduling error alone cannot pass.
        assert.equal(starts[0], clock); // Each player owns its own schedule.
        assert.ok(starts.every((time, i) => i === 0 || time > starts[i - 1]));
        assert.ok(starts.at(-1) < clock + 0.02);
      }
      clock += 1;
      engine.trigger({ type: 'cut' });
      assert.equal(player('splash').starts.at(-1), clock);
    } finally { engine.dispose(); }
  });

  await t.test('voice recovery waits for the final scheduled start plus clip duration', async context => {
    context.mock.timers.enable({ apis: ['setTimeout'] });
    const engine = createAudioEngine(); await engine.start();
    try {
      const music = nodes.find(node => node instanceof Filter).destination;
      for (let i = 0; i < 10; i++) engine.trigger({ type: 'narrate', clip: 'voice_alarm' });
      context.mock.timers.tick(1001);
      assert.ok(music.gain.value < 1);
      context.mock.timers.tick(10);
      assert.equal(music.gain.value, 1);
    } finally { engine.dispose(); }
  });

  await t.test('playback failure stays silent and a later event can retry', async context => {
    const engine = createAudioEngine(); await engine.start();
    try {
      const splash = player('splash');
      const broken = context.mock.method(splash, 'start', fail);
      assert.doesNotThrow(() => engine.trigger({ type: 'cut' }));
      broken.mock.restore();
      engine.trigger({ type: 'cut' });
      assert.equal(splash.starts.length, 1);
      assert.ok(splash.starts[0] > clock); // The failed attempt reserved its timestamp.
    } finally { engine.dispose(); }
  });

  await t.test('failed speech releases ducking and delayed errors stay inside audio', async context => {
    context.mock.timers.enable({ apis: ['setTimeout'] });
    const engine = createAudioEngine(); await engine.start();
    try {
      const music = nodes.find(node => node instanceof Filter).destination;
      context.mock.method(player('voice_alarm'), 'start', fail);
      engine.trigger({ type: 'alarm' });
      assert.doesNotThrow(() => context.mock.timers.tick(1081));
      assert.equal(music.gain.value, 1);
      context.mock.method(Param.prototype, 'rampTo', fail);
      engine.trigger({ type: 'all_clear' });
      assert.doesNotThrow(() => context.mock.timers.tick(1081));
    } finally { engine.dispose(); }
  });

  await t.test('update, mute and disposal errors cannot escape or prevent remaining cleanup', async context => {
    const engine = createAudioEngine(); await engine.start();
    context.mock.method(Param.prototype, 'rampTo', fail);
    assert.doesNotThrow(() => engine.update(frame));
    assert.doesNotThrow(() => engine.setMuted(true));
    context.mock.method(nodes[0], 'dispose', fail);
    assert.doesNotThrow(() => engine.dispose());
    assert.ok(nodes.slice(1).every(node => node.disposed));
    assert.doesNotThrow(() => engine.dispose());
  });

  await t.test('unlock failure resolves quietly and permits a later click to retry', async context => {
    const engine = createAudioEngine();
    const broken = context.mock.method(tone, 'start', async () => fail());
    await assert.doesNotReject(engine.start());
    broken.mock.restore();
    await engine.start();
    assert.equal(player('sea_calm').starts.length, 1);
    engine.dispose();
  });

  await t.test('partial initialization failure cleans up before retry', async context => {
    const engine = createAudioEngine();
    const broken = context.mock.method(Player.prototype, 'start', fail);
    await assert.doesNotReject(engine.start());
    assert.ok(nodes.every(node => node.disposed));
    broken.mock.restore();
    nodes = [];
    await engine.start();
    assert.equal(player('sea_calm').starts.length, 1);
    engine.dispose();
  });

  await t.test('delayed melody note errors cannot escape the timer', async context => {
    context.mock.timers.enable({ apis: ['setTimeout'] });
    const engine = createAudioEngine(); await engine.start();
    try {
      engine.update(frame);
      clock += 1;
      engine.update({ ...frame, minuteIndex: 1, price: 99.2 });
      context.mock.method(Synth.prototype, 'triggerAttackRelease', fail);
      assert.doesNotThrow(() => context.mock.timers.tick(500));
    } finally { engine.dispose(); }
  });
});
