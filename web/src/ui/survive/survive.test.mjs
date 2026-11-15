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

const tutorial = await load(new URL("./tutorialCards.ts", import.meta.url));
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

// ---------- 3. the coach reads only past frames ----------

const coach = await load(new URL("./coachLine.ts", import.meta.url));
const lineAt = (b, leverage, presses, f) => coach.coachLine(coach.pastOf(b, game.simulate(b, leverage, presses.filter((a) => a.i <= f)), f));

test("coach: pastOf hands the coach frames 0..f only, and the margin call only once it has happened", async () => {
  const b = await fixture("coach.fixture.json");
  const sim = game.simulate(b, 25, []);
  assert.ok(sim.marginCallI !== null && sim.marginCallI > 12, "at 25x the fixture's fall sinks the ship after the alarm");
  for (const f of [0, 5, 12, sim.marginCallI - 1, sim.marginCallI, b.n - 1]) {
    const p = coach.pastOf(b, sim, f);
    for (const k of ["mid", "equity", "notional", "held", "liq", "restorable"]) assert.equal(p[k].length, f + 1, `${k} at ${f}`);
    assert.ok(p.events.every((e) => e.i <= f));
    assert.equal(p.sunkAt, f >= sim.marginCallI ? sim.marginCallI : null);
  }
});

test("coach: the line at frame f is the same whatever the storm does after f", async () => {
  const b = await fixture("coach.fixture.json");
  const presses = [
    { i: 12, kind: "cut" },
    { i: 35, kind: "restore" },
  ];
  for (const leverage of [5, 10, 25]) {
    for (const acts of [[], presses]) {
      for (let f = 0; f < b.n - 1; f++) {
        // Other futures: after f the price jumps 3% up or down (a margin call at f + 1 at 25x), spreads widen, a
        // squall and an all-clear appear.
        for (const jump of [1.03, 0.97]) {
          const other = structuredClone(b);
          for (let i = f + 1; i < b.n; i++) {
            other.series.mid[i] = b.series.mid[f] * jump;
            other.series.open[i] = b.series.mid[f] * jump;
            other.series.spread_bp[i] = 9;
          }
          other.events = [...b.events.filter((e) => e.i <= f), { i: f + 1, type: "squall", text: "later" }, { i: f + 2, type: "all_clear", text: "later" }];
          assert.deepEqual(lineAt(other, leverage, acts, f), lineAt(b, leverage, acts, f), `${leverage}x, ${acts.length} presses, frame ${f}, x${jump}`);
        }
      }
    }
  }
});

test("coach: plain words about the player's own state, numbers from the simulation", async () => {
  const b = await fixture("coach.fixture.json");
  const sim25 = game.simulate(b, 25, []);
  const sinkAt0 = Math.abs((sim25.liq[0] / b.series.mid[0] - 1) * 100).toFixed(1);
  const start = lineAt(b, 25, [], 0);
  assert.equal(start.kind, "leverage");
  assert.equal(start.text, `You're at 25x: a ${sinkAt0}% fall in USDJPY sinks you.`);
  assert.equal(sinkAt0, "1.5");
  const sim10 = game.simulate(b, 10, []);
  assert.equal(lineAt(b, 10, [], 0).text, `You're at 10x: a ${Math.abs((sim10.liq[0] / b.series.mid[0] - 1) * 100).toFixed(1)}% fall in USDJPY sinks you.`);

  const watch = lineAt(b, 10, [], 3);
  assert.equal(watch.kind, "watch");
  assert.equal(watch.text, "Storm watch: US CPI is due in 5 minutes. Scheduled news can move prices fast.");

  const alarm = lineAt(b, 10, [], 12);
  assert.equal(alarm.kind, "alarm");
  assert.equal(alarm.tone, "warn");
  assert.match(alarm.text, /^The alarm just sounded: a storm has started\. At 10x, a \d+\.\d% fall in USDJPY sinks you\. Cut \(C\) throws 75% overboard\.$/);
  assert.notEqual(lineAt(b, 10, [], 11).kind, "alarm", "not before the alarm's own frame");

  const calm = lineAt(b, 10, [{ i: 12, kind: "cut" }], 14);
  assert.equal(calm.kind, "alarm");
  assert.equal(calm.text, "The alarm just sounded, and your cargo is already cut. Hold steady.");
  const afterCut = lineAt(b, 10, [{ i: 12, kind: "cut" }], 12 + coach.COACH_HOLD);
  assert.equal(afterCut.kind, "cut");
  assert.match(afterCut.text, /^Cargo cut to 25%\. Now it takes a \d+\.\d% fall in USDJPY to sink you\./);

  const mc = sim25.marginCallI;
  const sunk = lineAt(b, 25, [], mc);
  assert.equal(sunk.kind, "sunk");
  const hhmm = new Date((b.t0 + mc * 60) * 1000).toISOString().slice(11, 16);
  assert.equal(sunk.text, `Margin call at ${hhmm} UTC: the broker closed your trade. You keep $${Math.round(sim25.equity[mc]).toLocaleString("en-US")}.`);
  assert.notEqual(lineAt(b, 25, [], mc - 1).kind, "sunk");

  assert.equal(lineAt(b, 10, [], 34).kind, "all_clear");
  assert.equal(lineAt(b, 10, [{ i: 12, kind: "cut" }], 34).text, "All clear: the storm has passed. Restore (R) brings your cargo back aboard.");
});

test("coach: a thin safety margin is called out once no event line holds the stage", async () => {
  const b = await fixture("coach.fixture.json");
  b.events = []; // no alarm to speak over it
  const sim = game.simulate(b, 25, []);
  const f = sim.marginCallI - 1;
  const l = lineAt(b, 25, [], f);
  assert.equal(l.kind, "low_buffer");
  assert.equal(l.tone, "danger");
  const buf = (sim.equity[f] - sim.maintenance * sim.notional[f]) / sim.equity[f];
  assert.ok(l.text.startsWith(`Your safety margin is down to ${Math.round(buf * 100)}% of your money.`), l.text);
  assert.ok(l.text.endsWith("Cut (C) to lighten the ship."), l.text);
});

// ---------- 4. the end card's words come from the run ----------

const endcard = await load(new URL("./endcard.ts", import.meta.url));
const runOf = (b, leverage, presses) => game.summarize(b, game.simulate(b, leverage, presses));
const usd = (x) => `$${Math.round(x).toLocaleString("en-US")}`;
const hm = (b, i) => `${new Date((b.t0 + i * b.step_s) * 1000).toISOString().slice(11, 16)} UTC`;

test("end card: sunk at 25x, while the alarm-follower stayed afloat", async () => {
  const b = await fixture("coach.fixture.json");
  const r = runOf(b, 25, []);
  assert.equal(r.sunk, true);
  assert.equal(r.followed.sunk, false);
  assert.equal(r.followed.cutI, 13, "the alarm at 12 fills its cut at the 13 open");
  assert.equal(
    endcard.whatHappened(b, r),
    `At 25x the price moved ${r.worstAdversePct.toFixed(1)}% against you and the broker closed your trade at ${hm(b, r.marginCallI)}. You kept ${usd(r.score)} of your $1.0M. You never cut.`,
  );
  assert.equal(
    endcard.alarmFollower(b, r),
    `The alarm sounded at ${hm(b, 12)}. The alarm-follower cut 75% at the ${hm(b, 13)} open and came home with ${usd(r.followed.equity)}, ${usd(r.followed.equity - r.score)} more than you.`,
  );
  assert.equal(endcard.lessonFor(b, r), `When the alarm sounds, lighten the ship first and think second: here a cut at the alarm would have kept ${usd(r.followed.equity)} afloat.`);
});

test("end card: afloat at 10x after a cut at the alarm; the lesson counts what the cut kept", async () => {
  const b = await fixture("coach.fixture.json");
  const r = runOf(b, 10, [{ i: 12, kind: "cut" }]);
  assert.equal(r.sunk, false);
  assert.ok(r.score > r.held.equity);
  assert.equal(
    endcard.whatHappened(b, r),
    `You rode out the storm at 10x and came home with ${usd(r.score)} (${r.changePct.toFixed(1)}%). At the worst moment, ${hm(b, r.worstAdverseI)}, the price was ${r.worstAdversePct.toFixed(1)}% against you. You cut 75% of the cargo at ${hm(b, 13)}.`,
  );
  assert.equal(endcard.lessonFor(b, r), `Cutting when the sea turned kept ${usd(r.score - r.held.equity)} more than holding everything.`);
  assert.ok(endcard.alarmFollower(b, r).endsWith("than you.") || endcard.alarmFollower(b, r).endsWith("the same as you."));
});

test("end card: other runs give other lessons, each from the numbers", async () => {
  const b = await fixture("coach.fixture.json");
  const held = runOf(b, 10, []);
  assert.equal(endcard.lessonFor(b, held), `At 10x you rode out a ${held.worstAdversePct.toFixed(1)}% move against you with room to spare: your leverage decides how much room you have.`);
  // The same storm upside down (USDJPY rises): it blew the player's way.
  const up = structuredClone(b);
  const m0 = b.series.mid[0];
  up.series.mid = b.series.mid.map((m) => 2 * m0 - m);
  up.series.open = b.series.open.map((m) => 2 * m0 - m);
  const lucky = runOf(up, 10, []);
  assert.equal(lucky.worstAdversePct, 0);
  assert.equal(endcard.lessonFor(up, lucky), `This storm blew your way, but leverage works both ways: at 10x a ${Math.abs(lucky.line.movePct).toFixed(1)}% move against you would have sunk you.`);
  // No alarm in the bundle: nothing for the follower to act on, and the lesson is about leverage.
  const quiet = { ...b, events: [] };
  const sunk = runOf(quiet, 25, []);
  assert.equal(endcard.alarmFollower(quiet, sunk), "This storm raised no alarm, so the alarm-follower had nothing to act on.");
  assert.ok(endcard.lessonFor(quiet, sunk).startsWith("At 25x a 1.5% move against you was enough to sink you"), endcard.lessonFor(quiet, sunk));
});

test("end card: the share line carries the storm, difficulty, leverage, result and the follower; the link opens Survive", async () => {
  const b = await fixture("coach.fixture.json");
  const r = runOf(b, 25, []);
  const url = endcard.shareUrl("https://example.test/app/?storm=other&at=12#x", b.storm_id);
  assert.equal(url, "https://example.test/app/?mode=survive&storm=coach-fixture");
  assert.equal(
    endcard.shareLine(b, r, "Hard", url),
    `Sif Survive · USDJPY, coach fixture (Hard) · 25x · Sunk ${usd(r.score)} (${r.changePct.toFixed(1)}%) · alarm-follower ${usd(r.followed.equity)} · ${url}`,
  );
  const ok = runOf(b, 10, [{ i: 12, kind: "cut" }]);
  assert.ok(endcard.shareLine(b, ok, null).startsWith(`Sif Survive · USDJPY, coach fixture · 10x · Land ho! ${usd(ok.score)}`));
});
