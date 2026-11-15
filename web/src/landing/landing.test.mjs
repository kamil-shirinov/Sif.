// Landing page tests. Run: cd web && node --test src/landing/
// facts.ts and keys.ts import nothing at run time, so they are transpiled with web's own TypeScript and run as is.

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function load(name) {
  const src = await readFile(new URL(`./${name}.ts`, import.meta.url), "utf8");
  const js = ts.transpileModule(src, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);
}
const json = async (name) => JSON.parse(await readFile(new URL(`./fixtures/${name}`, import.meta.url), "utf8"));

const facts = await load("facts");
const keys = await load("keys");

// ---------- the numbers come from the data ----------

test("the three figures are read from index.json's metrics", async () => {
  const m = facts.readMetrics(await json("index.fixture.json"));
  const figs = facts.headlineFigures(m);
  assert.deepEqual(
    figs.map((f) => [f.key, f.value, f.of ?? null]),
    [
      ["alarmed", "5", "of 7"],
      ["caught", "3", "of 7"],
      ["false", "0.25", null],
    ],
  );
  assert.equal(figs[0].label, "storms alarmed in August");
  assert.deepEqual(figs[0].gauge, { lit: 5, total: 7 });
  assert.match(figs[0].meaning, /^Storms that raised/); // not "Every storm": 5 of 7 is not all
  assert.equal(figs[1].aside, "2 of 7 measured from the first onset");
  assert.equal(figs[2].meaning, "About one alert every 4 days with no storm behind it.");
  assert.equal(figs[2].aside, "0.40 a day counting each pair on its own");
  for (const f of figs) assert.match(f.href, /^https:\/\/github\.com\/kamil-shirinov\/stormscore\/blob\/main\/docs\/metrics\.md#/);
});

test("changing the data changes the figures, and missing metrics hide them", async () => {
  const raw = await json("index.fixture.json");
  raw.metrics.alarmed = 7;
  raw.metrics.false_alarm_episodes_per_day = 0;
  raw.metrics.split = "test: September 2026";
  const figs = facts.headlineFigures(facts.readMetrics(raw));
  assert.equal(figs[0].value, "7");
  assert.equal(figs[0].label, "storms alarmed in September");
  assert.match(figs[0].meaning, /^Every storm/);
  assert.equal(figs[2].value, "0.00");
  assert.equal(figs[2].meaning, "No false alert at all in the test month.");

  delete raw.metrics.caught;
  assert.deepEqual(facts.headlineFigures(facts.readMetrics(raw)).map((f) => f.key), ["alarmed", "false"]);
  raw.metrics = null;
  assert.equal(facts.readMetrics(raw), null);
  assert.deepEqual(facts.headlineFigures(null), []);
});

test("the story's numbers are read from the bundle, the false alarm included", async () => {
  const s = facts.readStory(await json("headline.fixture.json"));
  assert.ok(s);
  assert.deepEqual(facts.storySentences(s), [
    "On 21 July USDJPY fell 1.2% in 11 minutes from 09:20 UTC, with no scheduled release nearby.",
    "The alarm sounded at 09:23 with 71.3% of the move still ahead; the prepared book cut 60% at every alarm, including the false one at 09:05, and restored at each all-clear.",
    "It finished at $812,345, $411,111 ahead of the book that ignored them, which was margin-called at 09:27.",
  ]);
  assert.equal(s.month, "July");
  assert.equal(s.unprepared, "$401,234");
  assert.equal(s.preparedLoss, "$187,655");
  assert.equal(s.start, "$1,000,000");
});

test("a story without a margin call or a false alarm says so, and a broken bundle gives none", async () => {
  const raw = await json("headline.fixture.json");
  raw.ships.unprepared.margin_call_i = null;
  raw.events = raw.events.filter((e) => e.i !== 5);
  raw.series.unprepared_equity[raw.n - 1] = 900_000;
  const [, two, three] = facts.storySentences(facts.readStory(raw));
  assert.doesNotMatch(two, /false/);
  assert.equal(three, "It finished at $812,345, $87,655 behind the book that ignored them.");
  raw.series.prepared_equity = [1];
  assert.equal(facts.readStory(raw), null);
  assert.equal(facts.readStory(null), null);
});

test("the picker lists the other storms from the index", async () => {
  const raw = await json("index.fixture.json");
  const entries = facts.pickerEntries(raw.storms, "usdjpy-2026-07-30");
  assert.deepEqual(
    entries.map((e) => [e.id, e.symbol, e.when, e.move, e.kind]),
    [
      ["eurusd-2026-08-07", "EURUSD", "7 August 2026", "+0.5%", "scheduled"],
      ["nvda-2026-11-12", "NVDA", "12 November 2026", "-14.4%", "unscheduled"],
    ],
  );
});

test("the landing component types no figure: none of the real backtest's numbers appear in its source", async () => {
  const src = await readFile(new URL("./Landing.tsx", import.meta.url), "utf8");
  for (const typed of ["6 of 6", "4 of 6", "0.33", "0.51", "762,899", "494,551", "268,348", "89.0", "13:37", "10:18", "14:05", "2.9%", "75%"]) {
    assert.ok(!src.includes(typed), `Landing.tsx types "${typed}"`);
  }
});

// ---------- presenter keys ----------

const press = (key, extra = {}) => ({ key, ...extra });

test("presenter keys map to their actions", () => {
  const a = keys.presenterAction;
  assert.equal(a(press("l"), false), "landing");
  assert.equal(a(press("L"), false), "landing");
  assert.equal(a(press("l"), true), null); // already there
  assert.equal(a(press("1"), true), "headline");
  assert.equal(a(press("1"), false), "headline");
  assert.equal(a(press("2"), false), "survive");
  assert.equal(a(press("3"), true), "nvda");
  assert.equal(a(press("Escape"), true), "close");
  assert.equal(a(press("Escape"), false), null); // the storm picker keeps its own Esc
});

test("Space, C and R stay with the replay and Survive; modifiers, repeats and fields are ignored", () => {
  const a = keys.presenterAction;
  for (const k of [" ", "c", "C", "r", "R", "4", "Enter"]) {
    assert.equal(a(press(k), false), null, k);
    assert.equal(a(press(k), true), null, k);
  }
  assert.equal(a(press("1", { ctrlKey: true }), false), null);
  assert.equal(a(press("l", { metaKey: true }), false), null);
  assert.equal(a(press("2", { altKey: true }), false), null);
  assert.equal(a(press("1", { repeat: true }), false), null);
  assert.equal(a(press("l", { target: { tagName: "input" } }), false), null);
  assert.equal(a(press("3", { target: { tagName: "TEXTAREA" } }), false), null);
  assert.equal(a(press("2", { target: { tagName: "SELECT" } }), false), null);
  assert.equal(a(press("1", { target: { tagName: "DIV", isContentEditable: true } }), false), null);
  assert.equal(a(press("1", { target: { tagName: "BUTTON" } }), false), "headline");
});

test("bindPresenterKeys runs the action, prevents the default, and unbinds", () => {
  const target = new EventTarget();
  let landing = true;
  const ran = [];
  const unbind = keys.bindPresenterKeys(target, () => landing, (x) => ran.push(x));
  const fire = (key) => {
    const ev = new Event("keydown", { cancelable: true });
    ev.key = key;
    target.dispatchEvent(ev);
    return ev.defaultPrevented;
  };
  assert.equal(fire("Escape"), true);
  landing = false;
  assert.equal(fire("Escape"), false);
  assert.equal(fire(" "), false);
  assert.equal(fire("l"), true);
  assert.equal(fire("2"), true);
  unbind();
  fire("3");
  assert.deepEqual(ran, ["close", "landing", "survive"]);
});
