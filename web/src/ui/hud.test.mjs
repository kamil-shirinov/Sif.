// HUD tests: the captions, the scrubber's ticks, the end card and the stress rows come from the bundle, and H toggles
// the clean view. Run: cd web && node --test src/ui/
// story.ts imports only lib/format.ts (and derive.ts only types), so each file is transpiled with web's own TypeScript
// and its relative imports are loaded the same way.

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const cache = new Map();
async function load(url) {
  const key = url.href;
  if (cache.has(key)) return cache.get(key);
  let src = await readFile(url, "utf8");
  let js = ts.transpileModule(src, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
  // Point each relative import at its own transpiled module (a data: URL cannot resolve relative paths).
  const specs = [...js.matchAll(/from\s+"(\.{1,2}\/[^"]+)"/g)].map((m) => m[1]);
  for (const spec of new Set(specs)) {
    const dep = await load(new URL(`${spec}.ts`, url));
    js = js.split(`"${spec}"`).join(`"${dep.__url}"`);
  }
  const dataUrl = `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`;
  const mod = { ...(await import(dataUrl)), __url: dataUrl };
  cache.set(key, mod);
  return mod;
}
const json = async (name) => JSON.parse(await readFile(new URL(`./fixtures/${name}`, import.meta.url), "utf8"));

const story = await load(new URL("./story.ts", import.meta.url));
const { derive } = await load(new URL("../lib/derive.ts", import.meta.url));

/** The ships' cuts and restores as the scene plays them (the events, else ships.*.cut_i / restore_i). */
const actionsOf = (b) => {
  const d = derive(b);
  return { prepared: d.ships.prepared.actions, unprepared: d.ships.unprepared.actions };
};
const captions = (b) => story.storyEvents(b, actionsOf(b)).map((e) => story.captionLine(b, e));

// ---------- captions ----------

test("captions are built from bundle A's events, in order, with its times and numbers", async () => {
  const a = await json("story-a.fixture.json");
  assert.deepEqual(captions(a), [
    "10:03 · Storm watch: US Employment Situation due at 10:08",
    "10:07 · A squall: a sharp move against the book, no cut",
    "10:10 · The alarm fires with 82% of the move still ahead",
    "10:11 · The prepared ship cuts 75% of its cargo",
    "10:18 · Margin call: the unprepared ship goes down",
    "10:21 · Fair wind: a sharp move in the book's favour",
    "10:24 · All clear: the storm has passed",
    "10:25 · The prepared ship hoists its cargo back aboard",
  ]);
});

test("bundle B, with different numbers, gives different captions: nothing is typed in", async () => {
  const b = await json("story-b.fixture.json");
  // No cut events: the cut comes from ships.prepared.cut_i (frame 6) with its own cut_fraction (40%).
  // The alarm has move_ahead_pct null (a false alarm): no share is claimed. No margin call, no restore.
  assert.deepEqual(captions(b), [
    "14:35 · The alarm fires",
    "14:36 · The prepared ship cuts 40% of its cargo",
    "14:50 · All clear: the storm has passed",
  ]);
});

test("changing a number in the bundle changes the caption", async () => {
  const a = await json("story-a.fixture.json");
  a.ships.prepared.cut_fraction = 0.5;
  a.events.find((e) => e.type === "alarm").move_ahead_pct = 33.2;
  a.t0 += 3600; // an hour later
  const lines = captions(a);
  assert.ok(lines.includes("11:11 · The prepared ship cuts 50% of its cargo"));
  assert.ok(lines.includes("11:10 · The alarm fires with 33% of the move still ahead"));
});

test("a margin call given only as ships.*.margin_call_i still gets a caption, once", async () => {
  const a = await json("story-a.fixture.json");
  a.events = a.events.filter((e) => e.type !== "margin_call");
  const mc = captions(a).filter((l) => l.includes("Margin call"));
  assert.deepEqual(mc, ["10:18 · Margin call: the unprepared ship goes down"]);
});

test("a caption fires when the playhead crosses its frame, not before", async () => {
  const a = await json("story-a.fixture.json");
  const ev = story.storyEvents(a, actionsOf(a));
  assert.deepEqual(story.crossed(ev, 9, 10).map((e) => e.kind), ["alarm"]);
  assert.deepEqual(story.crossed(ev, 10, 11).map((e) => e.kind), ["cut"]);
  assert.deepEqual(story.crossed(ev, 11, 17), []);
  assert.deepEqual(story.crossed(ev, -1, 3).map((e) => e.kind), ["watch"]);
});

test("ticks: events within a few frames share one tick; every event type has a colour", async () => {
  const a = await json("story-a.fixture.json");
  const ev = story.storyEvents(a, actionsOf(a));
  const groups = story.groupTicks(ev, 1);
  assert.deepEqual(groups.map((g) => g.map((e) => e.kind)), [["watch"], ["squall"], ["alarm", "cut"], ["margin_call"], ["fair_wind"], ["all_clear", "restore"]]);
  for (const k of ["watch", "alarm", "squall", "fair_wind", "cut", "restore", "margin_call", "all_clear"]) assert.match(story.STORY_COLORS[k], /^#[0-9a-f]{6}$/);
});

// ---------- end card ----------

test("end card A: final equities from the series' last frame, the difference, the margin call and its time", async () => {
  const a = await json("story-a.fixture.json");
  const f = story.endFacts(a);
  const [p, u] = f.ships;
  assert.equal(p.label, "Followed the alarm");
  assert.equal(p.final, a.series.prepared_equity[a.n - 1]); // 971,000
  assert.equal(p.final, 971000);
  assert.equal(u.final, 640000);
  assert.equal(p.marginCall, null);
  assert.deepEqual(u.marginCall, { i: 18, time: "10:18 UTC" });
  assert.equal(f.diff, 331000);
  assert.equal(f.verdict, "Following the alarm kept $331,000 more");
  assert.equal(p.changePct.toFixed(1), "-2.9");
  assert.equal(u.changePct.toFixed(1), "-36.0");
});

test("end card B: other numbers, no margin call, and the honest verdict when ignoring did better", async () => {
  const b = await json("story-b.fixture.json");
  const f = story.endFacts(b);
  const [p, u] = f.ships;
  assert.equal(p.label, "Heeded the warning");
  assert.equal(u.label, "Sailed on");
  assert.equal(p.final, 514500);
  assert.equal(u.final, 526100);
  assert.equal(p.marginCall, null);
  assert.equal(u.marginCall, null);
  assert.equal(f.diff, -11600);
  assert.equal(f.verdict, "Ignoring the alarm kept $11,600 more");
});

test("end card: a margin call only in the events still shows, with the event's time", async () => {
  const a = await json("story-a.fixture.json");
  a.ships.unprepared.margin_call_i = null;
  a.events.find((e) => e.type === "margin_call").i = 19;
  assert.deepEqual(story.endFacts(a).ships[1].marginCall, { i: 19, time: "10:19 UTC" });
});

// ---------- stress rows ----------

test("stress rows shorten to one line and keep the backend's text as the tooltip", async () => {
  const a = await json("story-a.fixture.json");
  assert.equal(story.stressLine(a.stress[0]), "USDJPY 2 Jul 12:20 −58 bp → −$118k, afloat");
  assert.equal(story.stressLine(a.stress[1]), "EURUSD 15 Jul 08:31 +73 bp → −$150k, margin call");
  assert.equal(story.shortStress(a.stress[1]).full, a.stress[1].scenario);
  // Anything else is kept whole.
  assert.equal(story.stressLine({ scenario: "Synthetic storm replay", pnl_usd: -504136, margin_call: true }), "Synthetic storm replay → −$504k, margin call");
  assert.equal(story.shortStress({ scenario: "NVDA 11 Nov close to 12 Nov low: -4.2%, applied to AAPL", pnl_usd: 1200, margin_call: false }).move, "−4.2%");
});

// ---------- H: presenter clean view ----------

test("H (either case) toggles the clean view; nothing else does", () => {
  assert.equal(story.isCleanViewKey({ key: "h" }), true);
  assert.equal(story.isCleanViewKey({ key: "H" }), true);
  for (const key of ["l", "L", "1", "2", "3", "Escape", " ", "c", "C", "r", "R", "j"]) assert.equal(story.isCleanViewKey({ key }), false, key);
  assert.equal(story.isCleanViewKey({ key: "h", ctrlKey: true }), false);
  assert.equal(story.isCleanViewKey({ key: "h", metaKey: true }), false);
  assert.equal(story.isCleanViewKey({ key: "h", altKey: true }), false);
  assert.equal(story.isCleanViewKey({ key: "h", repeat: true }), false);
  assert.equal(story.isCleanViewKey({ key: "h", target: { tagName: "input" } }), false);
  assert.equal(story.isCleanViewKey({ key: "h", target: { tagName: "TEXTAREA" } }), false);
  assert.equal(story.isCleanViewKey({ key: "h", target: { tagName: "DIV", isContentEditable: true } }), false);
  assert.equal(story.isCleanViewKey({ key: "h", target: { tagName: "BUTTON" } }), true);
});

test("bound to a target, H toggles on and off again, and unbinding stops it", () => {
  const target = new EventTarget();
  let clean = false;
  const unbind = story.bindCleanViewKey(target, () => (clean = !clean));
  const press = (key, extra = {}) => {
    const ev = new Event("keydown", { cancelable: true });
    Object.assign(ev, { key, ...extra });
    target.dispatchEvent(ev);
    return ev;
  };
  const first = press("h");
  assert.equal(clean, true);
  assert.equal(first.defaultPrevented, true);
  press("H");
  assert.equal(clean, false);
  const other = press("L");
  assert.equal(clean, false);
  assert.equal(other.defaultPrevented, false); // L stays the landing's
  press("h", { repeat: true });
  assert.equal(clean, false);
  unbind();
  press("h");
  assert.equal(clean, false);
});

// ---------- chart labels: unique keys ----------

const chart = await load(new URL("./chartMarkers.ts", import.meta.url));

test("chart: both ships margin-called on the same minute get unique keys and one shared label", async () => {
  const b = await json("story-two-calls.fixture.json"); // both ships' margin calls at minute 18, as on INTC (189)
  const d = derive(b);
  const markers = chart.chartMarkers(b, d, null, 1);
  const keys = markers.map((m) => m.key);
  assert.equal(new Set(keys).size, keys.length, `duplicate key in ${keys.join(", ")}`);
  const calls = markers.filter((m) => m.text === "Margin call");
  assert.deepEqual(
    calls.map((m) => [m.i, m.key, m.repeat]),
    [
      [18, "18-Margin call", false],
      [18, "18-Margin call#1", true],
    ],
  );
  // The keys are stable: building the markers again gives the same ones.
  assert.deepEqual(chart.chartMarkers(b, d, null, 1).map((m) => m.key), keys);
  // Every other storm keeps its plain "minute-text" keys.
  const a = await json("story-a.fixture.json");
  for (const m of chart.chartMarkers(a, derive(a), null, 1)) assert.equal(m.key, `${m.i}-${m.text}`);
});

// ---------- toasts: at most two, throttled ----------

const tq = await load(new URL("./toastQueue.ts", import.meta.url));

test("toasts: a 16x burst shows at most two, keeps the most important waiting, and rotates no faster than the minimum", () => {
  let s = tq.emptyToasts();
  let id = 0;
  const push = (kind, now) => (s = tq.pushToastQ(s, { id: id++, kind }, now));
  // Story A's events at 16x (4 frames a second x 16 = 64 frames a second): watch, squall, alarm, cut, margin call,
  // fair wind, all clear, restore arrive within about 0.4 s.
  const kinds = ["watch", "squall", "alarm", "cut", "margin_call", "fair_wind", "all_clear", "restore"];
  kinds.forEach((k, j) => {
    push(k, j * 50);
    assert.ok(s.visible.length <= tq.MAX_VISIBLE, "never more than two on screen");
    assert.ok(s.queue.length <= tq.QUEUE_MAX);
  });
  assert.deepEqual(s.visible.map((v) => v.toast.kind), ["watch", "squall"]);
  // The queue kept the two most important that arrived: the margin call and the all-clear.
  assert.deepEqual(s.queue.map((t) => t.kind).sort(), ["all_clear", "margin_call"]);
  // Before the oldest has been up the minimum, nothing rotates.
  s = tq.tickToastQ(s, tq.MIN_SHOW_MS - 1);
  assert.deepEqual(s.visible.map((v) => v.toast.kind), ["watch", "squall"]);
  // Then the margin call replaces the oldest, and the all-clear waits for the next turn.
  s = tq.tickToastQ(s, tq.MIN_SHOW_MS);
  assert.deepEqual(s.visible.map((v) => v.toast.kind), ["squall", "margin_call"]);
  assert.deepEqual(s.queue.map((t) => t.kind), ["all_clear"]);
  s = tq.tickToastQ(s, tq.MIN_SHOW_MS + 100); // the squall went up at 50 ms: its turn ends at 1650
  assert.deepEqual(s.visible.map((v) => v.toast.kind), ["margin_call", "all_clear"]);
  assert.equal(s.queue.length, 0);
});

test("toasts: at 1x every toast shows, and a dropped toast frees its slot at once", () => {
  let s = tq.emptyToasts();
  s = tq.pushToastQ(s, { id: 1, kind: "alarm" }, 0);
  s = tq.pushToastQ(s, { id: 2, kind: "cut" }, 4000);
  assert.deepEqual(s.visible.map((v) => v.toast.id), [1, 2]);
  s = tq.pushToastQ(s, { id: 3, kind: "margin_call" }, 5000); // the alarm has been up 5 s: it makes way
  assert.deepEqual(s.visible.map((v) => v.toast.id), [2, 3]);
  s = tq.pushToastQ(s, { id: 4, kind: "fair_wind" }, 5100); // the cut has been up 1.1 s only: it waits
  assert.deepEqual(s.queue.map((t) => t.id), [4]);
  s = tq.dropToastQ(s, 2, 5200); // the cut's lifetime ends: the fair wind takes the slot
  assert.deepEqual(s.visible.map((v) => v.toast.id), [3, 4]);
  assert.equal(s.queue.length, 0);
  assert.equal(tq.tickToastQ(s, 9999), s, "nothing waiting: the same state, no re-render");
});

// Survive for beginners (tutorial, difficulty, coach, end card): src/ui/survive/survive.test.mjs, run with these.
await import("./survive/survive.test.mjs");
