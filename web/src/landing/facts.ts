// Everything the landing page says with a number is built here, from index.json and the headline bundle as fetched.
// No number is typed into the page: these functions read the raw JSON leniently (a missing field hides its line) and
// return display strings. They import nothing at run time, so landing.test.mjs can run them under plain Node.

export const REPO_URL = "https://github.com/kamil-shirinov/stormscore";
export const METRICS_DOC = `${REPO_URL}/blob/main/docs/metrics.md`;
export const README_HONESTY = `${REPO_URL}/blob/main/README.md#honesty-notes`;
/** GitHub anchors of docs/metrics.md sections 5 (alarmed, caught) and 6 (false alarms). */
export const METRICS_ALARM_ANCHOR = `${METRICS_DOC}#5-alarmed-caught-minutes-from-onset-stormevaluate`;
export const METRICS_FALSE_ANCHOR = `${METRICS_DOC}#6-false-alarms-two-rates-each-labelled-exactly-stormevaluatescore`;

/** Presenter key 3. */
export const NVDA_STORM_ID = "nvda-2026-11-12";

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const int = (v: unknown): number | null => {
  const n = num(v);
  return n !== null && Number.isInteger(n) ? n : null;
};

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MONTH_RE = new RegExp(`(${MONTHS.join("|")})`, "i");

// ---------- index.json metrics ----------

/** The index.json metrics the landing shows (August, the test split). */
export interface LandingMetrics {
  /** The test month as the backtest's split label names it, e.g. "August"; null when it names none. */
  month: string | null;
  storms: number | null;
  alarmed: number | null;
  caught: number | null;
  caught_first_onset: number | null;
  false_alarm_episodes_per_day: number | null;
  false_alarms_per_day: number | null;
}

/** index.json's `metrics`, or null when the file has none (no backtest yet). */
export function readMetrics(rawIndex: unknown): LandingMetrics | null {
  if (!isObj(rawIndex) || !isObj(rawIndex.metrics)) return null;
  const m = rawIndex.metrics;
  const split = typeof m.split === "string" ? m.split : "";
  const month = MONTH_RE.exec(split)?.[1] ?? null;
  return {
    month: month ? month[0].toUpperCase() + month.slice(1).toLowerCase() : null,
    storms: int(m.storms),
    alarmed: int(m.alarmed),
    caught: int(m.caught),
    caught_first_onset: int(m.caught_first_onset),
    false_alarm_episodes_per_day: num(m.false_alarm_episodes_per_day),
    false_alarms_per_day: num(m.false_alarms_per_day),
  };
}

/** One of the three headline numbers. */
export interface Figure {
  key: "alarmed" | "caught" | "false";
  /** The big number, e.g. "6" or "0.33". */
  value: string;
  /** "of 6" for counts; absent for rates. */
  of?: string;
  /** For counts: lit and total segments of the gauge. */
  gauge?: { lit: number; total: number };
  label: string;
  /** One line in plain words. */
  meaning: string;
  /** A second, stricter or finer figure, in small type. */
  aside?: string;
  href: string;
}

/** "about one every 3 observed days" from a rate per day. */
function everyNDays(perDay: number): string {
  if (perDay <= 0) return "No false alert at all in the test month.";
  const days = 1 / perDay;
  const shown = days >= 1.5 ? String(Math.round(days)) : days.toFixed(1);
  return shown === "1" || shown === "1.0"
    ? "About one alert a day with no storm behind it."
    : `About one alert every ${shown} days with no storm behind it.`;
}

/** The three numbers, in order; a figure whose inputs are missing is left out. */
export function headlineFigures(m: LandingMetrics | null): Figure[] {
  if (!m) return [];
  const month = m.month ?? "the test month";
  const out: Figure[] = [];
  const total = m.storms;
  if (m.alarmed !== null && total !== null && total > 0) {
    out.push({
      key: "alarmed",
      value: String(m.alarmed),
      of: `of ${total}`,
      gauge: { lit: m.alarmed, total },
      label: `storms alarmed in ${month}`,
      meaning:
        m.alarmed === total
          ? "Every storm raised the alarm before the move bottomed out, in a month the detector never saw while it was tuned."
          : "Storms that raised the alarm before the move bottomed out, in a month the detector never saw while it was tuned.",
      href: METRICS_ALARM_ANCHOR,
    });
  }
  if (m.caught !== null && total !== null && total > 0) {
    out.push({
      key: "caught",
      value: String(m.caught),
      of: `of ${total}`,
      gauge: { lit: m.caught, total },
      label: "caught with at least half the move ahead",
      meaning: "When the alarm sounded, at least half of the fall was still to come: time to cut.",
      aside: m.caught_first_onset !== null ? `${m.caught_first_onset} of ${total} measured from the first onset` : undefined,
      href: METRICS_ALARM_ANCHOR,
    });
  }
  const ep = m.false_alarm_episodes_per_day;
  if (ep !== null) {
    out.push({
      key: "false",
      value: ep.toFixed(2),
      label: "false alert episodes per day",
      meaning: everyNDays(ep),
      aside: m.false_alarms_per_day !== null ? `${m.false_alarms_per_day.toFixed(2)} a day counting each pair on its own` : undefined,
      href: METRICS_FALSE_ANCHOR,
    });
  }
  return out;
}

// ---------- the headline bundle (30 July) ----------

export interface StoryFacts {
  symbol: string;
  /** "30 July" (the onset's UTC day). */
  date: string;
  month: string;
  /** "fell" or "rose". */
  verb: string;
  /** "2.9%" */
  move: string;
  /** Onset to trough, in minutes. */
  minutes: number;
  /** "13:29" UTC */
  onset: string;
  scheduled: boolean;
  event: string | null;
  /** The storm-level alarm credited to the storm, if any. */
  alarm: { time: string; ahead: string | null } | null;
  /** Alarms before the credited one, which cleared before the onset (July's scoring counts them as false). */
  earlier: string[];
  /** "75%" */
  cut: string | null;
  start: string;
  prepared: string;
  unprepared: string;
  /** Prepared final minus unprepared final, as "$268,348"; `ahead` says which way. */
  gap: string;
  ahead: boolean;
  /** Prepared start minus final, when it lost money. */
  preparedLoss: string | null;
  /** UTC time of each ship's margin call, or null. */
  preparedMarginCall: string | null;
  unpreparedMarginCall: string | null;
  /** Each ship's final equity as a share of its start (for the bars). */
  preparedShare: number;
  unpreparedShare: number;
}

export const fmtUsd = (x: number) => `${x < 0 ? "-" : ""}$${Math.round(Math.abs(x)).toLocaleString("en-US")}`;

function hhmm(epochS: number): string {
  const d = new Date(epochS * 1000);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

/** The facts of a replay bundle's story, read leniently; null when its core (series, ships, storm) is unusable. */
export function readStory(raw: unknown): StoryFacts | null {
  if (!isObj(raw) || !isObj(raw.storm) || !isObj(raw.series) || !isObj(raw.ships)) return null;
  const t0 = int(raw.t0);
  const step = int(raw.step_s);
  const n = int(raw.n);
  const st = raw.storm;
  const onsetI = int(st.onset_i);
  const troughI = int(st.trough_i);
  const moveBp = num(st.move_bp);
  if (t0 === null || step === null || step <= 0 || n === null || n < 2 || onsetI === null || troughI === null || moveBp === null) return null;
  const at = (i: number) => t0 + i * step;
  const prepEq = raw.series.prepared_equity;
  const unprepEq = raw.series.unprepared_equity;
  const prep = raw.ships.prepared;
  const unprep = raw.ships.unprepared;
  if (!Array.isArray(prepEq) || !Array.isArray(unprepEq) || prepEq.length !== n || unprepEq.length !== n || !isObj(prep) || !isObj(unprep)) return null;
  const prepFinal = num(prepEq[n - 1]);
  const unprepFinal = num(unprepEq[n - 1]);
  const start = num(prep.start_equity_usd);
  const unprepStart = num(unprep.start_equity_usd) ?? start;
  if (prepFinal === null || unprepFinal === null || start === null || start <= 0 || unprepStart === null || unprepStart <= 0) return null;

  const events = (Array.isArray(raw.events) ? raw.events : []).filter(isObj);
  const alarms = events
    .filter((e) => e.type === "alarm" && int(e.i) !== null)
    .map((e) => ({ i: int(e.i)!, ahead: num(e.move_ahead_pct) }))
    .sort((a, b) => a.i - b.i);
  // The credited alarm: the one storm.alarm_i names, else the first alarm whose move_ahead_pct is set (a matched one).
  const alarmI = int(st.alarm_i);
  const credited = (alarmI !== null ? alarms.find((a) => a.i === alarmI) : undefined) ?? alarms.find((a) => a.ahead !== null);
  let alarm: StoryFacts["alarm"] = null;
  if (credited) {
    const ahead = num(st.move_ahead_pct) ?? credited.ahead;
    alarm = { time: hhmm(at(credited.i)), ahead: ahead !== null ? `${ahead.toFixed(1)}%` : null };
  } else if (alarmI !== null) {
    const ahead = num(st.move_ahead_pct);
    alarm = { time: hhmm(at(alarmI)), ahead: ahead !== null ? `${ahead.toFixed(1)}%` : null };
  }
  const creditedI = credited?.i ?? alarmI;
  const earlier = creditedI === null ? [] : alarms.filter((a) => a.i < creditedI && a.i < onsetI).map((a) => hhmm(at(a.i)));

  const cutFraction = num(prep.cut_fraction);
  const onsetDate = new Date(at(onsetI) * 1000);
  const month = MONTHS[onsetDate.getUTCMonth()];
  const mcOf = (ship: Obj) => {
    const i = int(ship.margin_call_i);
    return i === null ? null : hhmm(at(i));
  };
  const gap = prepFinal - unprepFinal;

  return {
    symbol: typeof raw.symbol === "string" ? raw.symbol : "",
    date: `${onsetDate.getUTCDate()} ${month}`,
    month,
    verb: moveBp < 0 ? "fell" : "rose",
    move: `${Math.abs(moveBp / 100).toFixed(1)}%`,
    minutes: Math.round(((troughI - onsetI) * step) / 60),
    onset: hhmm(at(onsetI)),
    scheduled: st.kind === "scheduled",
    event: typeof st.event === "string" && st.event.trim() !== "" ? st.event : null,
    alarm,
    earlier,
    cut: cutFraction !== null && cutFraction > 0 ? `${Math.round(cutFraction * 100)}%` : null,
    start: fmtUsd(start),
    prepared: fmtUsd(prepFinal),
    unprepared: fmtUsd(unprepFinal),
    gap: fmtUsd(Math.abs(gap)),
    ahead: gap >= 0,
    preparedLoss: prepFinal < start ? fmtUsd(start - prepFinal) : null,
    preparedMarginCall: mcOf(prep),
    unpreparedMarginCall: mcOf(unprep),
    preparedShare: Math.max(0, prepFinal / start),
    unpreparedShare: Math.max(0, unprepFinal / unprepStart),
  };
}

const list = (xs: string[]) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

/** The story in three sentences, every number from `f`. */
export function storySentences(f: StoryFacts): [string, string, string] {
  const release = f.scheduled
    ? f.event
      ? `, close to the scheduled ${f.event} release`
      : ", close to a scheduled release"
    : ", with no scheduled release nearby";
  const one = `On ${f.date} ${f.symbol} ${f.verb} ${f.move} in ${f.minutes} minutes from ${f.onset} UTC${release}.`;

  const including =
    f.earlier.length === 0 ? "" : f.earlier.length === 1 ? `, including the false one at ${f.earlier[0]}` : `, including the false ones at ${list(f.earlier)}`;
  const cut = f.cut ? `cut ${f.cut} at every alarm${including}, and restored at each all-clear` : `followed every alarm${including}`;
  const two = f.alarm
    ? `The alarm sounded at ${f.alarm.time}${f.alarm.ahead ? ` with ${f.alarm.ahead} of the move still ahead` : ""}; the prepared book ${cut}.`
    : `The prepared book ${cut}.`;

  const mc = f.unpreparedMarginCall ? `, which was margin-called at ${f.unpreparedMarginCall}` : "";
  const three = `It finished at ${f.prepared}, ${f.gap} ${f.ahead ? "ahead of" : "behind"} the book that ignored them${mc}.`;
  return [one, two, three];
}

// ---------- the picker ----------

export interface PickerEntry {
  id: string;
  file: string;
  symbol: string;
  /** The title without its symbol, e.g. "2 July 2026". */
  when: string;
  /** "-2.9%" */
  move: string;
  down: boolean;
  kind: "scheduled" | "unscheduled";
}

interface IndexStormLike {
  storm_id: string;
  title: string;
  symbol: string;
  kind: "scheduled" | "unscheduled";
  move_bp: number;
  file: string;
}

/** The index's storms other than `exclude`, as picker entries. */
export function pickerEntries(storms: IndexStormLike[], exclude: string): PickerEntry[] {
  return storms
    .filter((s) => s.storm_id !== exclude)
    .map((s) => {
      const prefix = `${s.symbol}, `;
      const when = s.symbol && s.title.startsWith(prefix) ? s.title.slice(prefix.length) : s.title;
      return {
        id: s.storm_id,
        file: s.file,
        symbol: s.symbol || s.storm_id,
        when,
        move: `${s.move_bp > 0 ? "+" : s.move_bp < 0 ? "-" : ""}${Math.abs(s.move_bp / 100).toFixed(1)}%`,
        down: s.move_bp < 0,
        kind: s.kind,
      };
    });
}
