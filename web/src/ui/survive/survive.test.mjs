// Survive for beginners: the tutorial shows once, difficulty comes from the data, coach lines read only past frames,
// and the end card's lesson and share line come from the run. Run: cd web && node --test src/ui/survive/survive.test.mjs
// (src/ui/hud.test.mjs imports this file, so the web check runs it too). Each .ts file is transpiled with web's own
// TypeScript and its relative imports are loaded the same way, as in hud.test.mjs.

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const cache = new Map();
async function load(url) {
  const key = url.href;
  if (cache.has(key)) return cache.get(key);
  const src = await readFile(url, "utf8");
  let js = ts.transpileModule(src, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
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
const fixture = async (name) => JSON.parse(await readFile(new URL(`./fixtures/${name}`, import.meta.url), "utf8"));
const hudFixture = async (name) => JSON.parse(await readFile(new URL(`../fixtures/${name}`, import.meta.url), "utf8"));

const tutorial = await load(new URL("./tutorial.ts", import.meta.url));
const game = await load(new URL("../../lib/survive.ts", import.meta.url));

/** A Storage stand-in. */
function memoryStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => void m.set(k, String(v)), map: m };
}
const throwingStorage = {
  getItem() {
    throw new Error("SecurityError");
  },
  setItem() {
    throw new Error("QuotaExceededError");
  },
};

// ---------- 1. the tutorial shows once ----------

test("tutorial: shown on the first visit, never again once seen, on this device", () => {
  const storage = memoryStorage();
  const gate = tutorial.createTutorialGate(storage);
  assert.equal(gate.shouldShow(), true);
  assert.equal(gate.shouldShow(), true, "asking does not count as seeing it");
  gate.markSeen();
  assert.equal(gate.shouldShow(), false);
  assert.equal(storage.map.get(tutorial.TUTORIAL_KEY), "seen");
  // A reload: a new gate over the same storage.
  assert.equal(tutorial.createTutorialGate(storage).shouldShow(), false);
  // Another device (empty storage) sees it.
  assert.equal(tutorial.createTutorialGate(memoryStorage()).shouldShow(), true);
});

test("tutorial: blocked or missing storage never throws, and the cards still show only once per page", () => {
  for (const storage of [throwingStorage, null]) {
    const gate = tutorial.createTutorialGate(storage);
    assert.equal(gate.shouldShow(), true);
    assert.doesNotThrow(() => gate.markSeen());
    assert.equal(gate.shouldShow(), false);
  }
  assert.equal(tutorial.browserStorage(), null, "no window under Node");
});

test("tutorial: three cards whose numbers come from the game's maths on the loaded storm", async () => {
  const a = await hudFixture("story-a.fixture.json"); // USDJPY, FX: 10x by default, 2.5% maintenance
  const cards = tutorial.tutorialCards(a);
  assert.deepEqual(cards.map((c) => c.key), ["leverage", "line", "cut"]);
  const L = game.defaultLeverageFor(a);
  const line = game.marginLineFor(a, L);
  assert.equal(L, 10);
  assert.match(cards[0].text, /At 10x .* \$10\.0M of cargo/);
  assert.match(cards[0].text, /about 10%/);
  assert.ok(cards[1].text.includes(`${Math.abs(line.movePct).toFixed(1)}%`), cards[1].text);
  const after = tutorial.cutLineMovePct(a, L);
  assert.ok(Math.abs(after) > Math.abs(line.movePct), "a cut moves the line further away");
  assert.ok(cards[2].text.includes(`to ${Math.abs(after).toFixed(1)}% away`), cards[2].text);
  assert.match(cards[2].text, /75% of the cargo/);
  // An equity book (15% maintenance, 4x by default) gives other numbers: nothing is typed in.
  const eq = { ...a, asset_class: "equity", symbol: "NVDA" };
  const other = tutorial.tutorialCards(eq);
  assert.match(other[0].text, /At 4x/);
  assert.notEqual(other[1].text, cards[1].text);
});

// ---------- 2. difficulty comes from the data ----------

const difficulty = await load(new URL("./difficulty.ts", import.meta.url));

test("difficulty: index.json's move size rates each storm at the slider's starting leverage", async () => {
  const idx = await fixture("index.fixture.json");
  const r = Object.fromEntries(idx.storms.map((e) => [e.storm_id, difficulty.rate(difficulty.factsFromEntry(e))]));
  // EURUSD +0.47% x 10x = 4.7% of the money: Easy. USDSGD -1.21% x 10 = 12.1%: Medium. USDJPY -2.90% x 10 = 29%: Hard.
  // NVDA -14.4% x 4x (equity books start at 4x) = 57.6%: Hard.
  assert.equal(r["eurusd-2026-08-07"].level, "easy");
  assert.equal(r["usdsgd-2026-08-14"].level, "medium");
  assert.equal(r["usdjpy-2026-07-30"].level, "hard");
  assert.equal(r["nvda-2026-11-12"].level, "hard");
  assert.equal(r["nvda-2026-11-12"].leverage, 4);
  assert.equal(r["usdsgd-2026-08-14"].hitPct.toFixed(1), "12.1");
  assert.equal(r["usdjpy-2026-07-30"].fast, null, "no timing until the bundle is read");
  assert.equal(r["eurusd-2026-08-07"].sentence, "EURUSD rose 0.5%. At 10x that move is worth 5% of your money.");
  assert.equal(r["usdjpy-2026-07-30"].sentence, "USDJPY fell 2.9%. At 10x that move is worth 29% of your money.");
});

test("difficulty: change the move and the rating changes; nothing is typed in", async () => {
  const idx = await fixture("index.fixture.json");
  const eur = idx.storms.find((e) => e.storm_id === "eurusd-2026-08-07");
  const at = (bp) => difficulty.rate(difficulty.factsFromEntry({ ...eur, move_bp: bp })).level;
  assert.equal(at(99), "easy");
  assert.equal(at(-100), "medium"); // 10% of the money
  assert.equal(at(199), "medium");
  assert.equal(at(200), "hard");
  assert.equal(difficulty.rate(difficulty.factsFromEntry({ ...eur, asset_class: "equity", move_bp: 200 })).level, "easy"); // 2% x 4x = 8%
});

test("difficulty: a fast storm is one level harder; the bundle's onset and trough give the minutes", async () => {
  const a = await hudFixture("story-a.fixture.json"); // USDJPY, -100 bp, onset 5, trough 15: 10 minutes
  const f = difficulty.factsFromBundle(a);
  assert.equal(f.minutes, 10);
  assert.equal(f.moveBp, -100);
  const fast = difficulty.rate(f);
  assert.equal(fast.fast, true);
  assert.equal(fast.level, "hard", "10% of the money is Medium on size; in 10 minutes it is Hard");
  assert.equal(fast.sentence, "USDJPY fell 1.0% in 10 minutes. At 10x that move is worth 10% of your money, and it came too fast to think twice.");
  // The same move spread over 24 minutes of 400 s (160 minutes): Medium, as the size says.
  const slow = difficulty.rate(difficulty.factsFromBundle({ ...a, storm: { ...a.storm, trough_i: 29 }, step_s: 400 }));
  assert.equal(slow.fast, false);
  assert.equal(slow.level, "medium");
  assert.match(slow.sentence, /fell 1\.0% over 2\.7 hours\./);
  // An Easy storm that is fast becomes Medium; Hard stays Hard.
  const eurFast = difficulty.rate({ storm_id: "e", symbol: "EURUSD", asset_class: "fx", moveBp: 47, minutes: 12 });
  assert.equal(eurFast.level, "medium");
  assert.equal(difficulty.rate({ storm_id: "j", symbol: "USDJPY", asset_class: "fx", moveBp: -290.4, minutes: 3 }).level, "hard");
});

test("difficulty: minutes count only while the market trades", async () => {
  const a = await hudFixture("story-a.fixture.json");
  const open = Array.from({ length: a.n }, (_, i) => (i >= 8 && i <= 12 ? 0 : 1)); // 5 closed minutes inside the storm
  assert.equal(difficulty.factsFromBundle({ ...a, series: { ...a.series, market_open: open } }).minutes, 5);
});

test("difficulty: storms group Easy, Medium, Hard, the gentler first inside a level", async () => {
  const idx = await fixture("index.fixture.json");
  const rows = idx.storms.map((e) => ({ id: e.storm_id, rating: difficulty.rate(difficulty.factsFromEntry(e)) }));
  const groups = difficulty.groupByDifficulty(rows);
  assert.deepEqual(
    groups.map((g) => [g.level, g.rows.map((r) => r.id)]),
    [
      ["easy", ["eurusd-2026-08-07"]],
      ["medium", ["usdsgd-2026-08-14"]],
      ["hard", ["usdjpy-2026-07-30", "nvda-2026-11-12"]],
    ],
  );
});
