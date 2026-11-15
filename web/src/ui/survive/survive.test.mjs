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
