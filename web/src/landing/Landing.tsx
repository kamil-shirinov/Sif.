import { useEffect, type CSSProperties, type MouseEvent, type ReactNode } from "react";
import { useApp } from "../state/app";
import { HEADLINE_STORM_ID } from "../lib/session";
import { closeLanding, openFromLanding, startExplorer } from "./actions";
import {
  headlineFigures,
  NVDA_STORM_ID,
  pickerEntries,
  README_HONESTY,
  REPO_URL,
  storySentences,
  type Figure,
  type StoryFacts,
} from "./facts";
import { useLandingData } from "./useLandingData";
import "../landing.css";
import "./transition.css";

/** A plain click runs `go` in place (the canvas and sound stay warm); a modified click opens the link as a link. */
function inApp(go: () => void) {
  return (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    go();
  };
}

const delay = (k: number) => ({ "--d": `${k * 70}ms` }) as CSSProperties;

function SectionHead({ n, children }: { n: string; children: ReactNode }) {
  return (
    <h2 className="lp-head">
      <span className="lp-head-n">{n}</span>
      <span>{children}</span>
    </h2>
  );
}

function Gauge({ lit, total }: { lit: number; total: number }) {
  const cells = Math.max(1, Math.min(total, 40));
  return (
    <span className="lp-gauge" aria-hidden="true">
      {Array.from({ length: cells }, (_, i) => (
        <span key={i} className={i < lit ? "on" : ""} />
      ))}
    </span>
  );
}

function FigureCard({ f, k }: { f: Figure; k: number }) {
  return (
    <a className={`lp-fig lp-fig-${f.key} lp-rise`} style={delay(k)} href={f.href} target="_blank" rel="noreferrer">
      <span className="lp-fig-value">
        <span className="lp-fig-n">{f.value}</span>
        {f.of && <span className="lp-fig-of">{f.of}</span>}
      </span>
      {f.gauge ? <Gauge lit={f.gauge.lit} total={f.gauge.total} /> : <span className="lp-gauge lp-gauge-none" aria-hidden="true" />}
      <span className="lp-fig-label">{f.label}</span>
      <span className="lp-fig-meaning">{f.meaning}</span>
      {f.aside && <span className="lp-fig-aside">{f.aside}</span>}
      <span className="lp-fig-link">definition ↗</span>
    </a>
  );
}

function Ledger({ s }: { s: StoryFacts }) {
  const w = (share: number) => ({ "--w": `${Math.min(1, share) * 100}%` }) as CSSProperties;
  return (
    <div className="lp-ledger" aria-label="The two ships' final equity">
      <div className="lp-ledger-row prepared">
        <span className="lp-ledger-name">Followed every alarm</span>
        <span className="lp-ledger-usd">{s.prepared}</span>
        <span className="lp-ledger-bar" style={w(s.preparedShare)} />
        <span className="lp-ledger-note">
          {s.preparedMarginCall ? `margin call at ${s.preparedMarginCall}` : s.preparedLoss ? `lost ${s.preparedLoss}: a defence, not a profit` : "afloat"}
        </span>
      </div>
      <div className="lp-ledger-row unprepared">
        <span className="lp-ledger-name">Ignored them</span>
        <span className="lp-ledger-usd">{s.unprepared}</span>
        <span className="lp-ledger-bar" style={w(s.unpreparedShare)} />
        <span className="lp-ledger-note">{s.unpreparedMarginCall ? `margin call at ${s.unpreparedMarginCall}` : "afloat"}</span>
      </div>
      <div className="lp-ledger-foot">Both started at {s.start} · synthetic book</div>
    </div>
  );
}

const DEFENCES = [
  { cls: "watch", name: "Warn ahead", line: "Scheduled releases come from a public calendar, so a watch opens before the release does." },
  { cls: "storm", name: "Alarm in the first minutes", line: "For the unscheduled ones, code fires the alarm once the move is under way, with most of it still ahead." },
  { cls: "calm", name: "Prepare the book", line: "Exposure, margin buffer and stress tests, so the cut is already decided when the alarm sounds." },
];

const STACK = [
  { name: "SGX", role: "one-minute FX bars, spot and forwards" },
  { name: "Tiger Data", role: "TimescaleDB hypertables behind the live chart" },
  { name: "ElevenLabs", role: "the sea, the storm and the voices" },
  { name: "Meta", role: "Muse Spark writes the storm report" },
  { name: "Fireworks", role: "a second model family inspects it" },
  { name: "Modal", role: "private mode on open weights" },
];

const HONESTY = [
  { b: "The book is synthetic.", t: "An invented trader position, labelled as such; no personal data." },
  { b: "July is in-sample.", t: "The detector was tuned on July. August is the test." },
  { b: "Onset is defined in hindsight,", t: "as the strongest window, so first_onset is reported next to it." },
  { b: "No price predictions.", t: "The alarm says a storm is under way; the calendar says one may be near." },
];

const KEYS: [string, string][] = [
  ["Enter", "Start"],
  ["E", "Explorer"],
  ["L", "landing"],
  ["1", "30 July"],
  ["2", "Survive"],
  ["3", "NVDA"],
  ["Esc", "close"],
];

/** `motion`: "leave" while the page gives way to the replay, "enter" while it comes back (landing/transition.ts). */
export function Landing({ motion = null }: { motion?: "leave" | "enter" | null }) {
  const { metrics, story } = useLandingData();
  const index = useApp((s) => s.index);
  const busy = useApp((s) => s.loadingStorm);
  const figures = headlineFigures(metrics ?? null);
  const others = pickerEntries(index?.storms ?? [], HEADLINE_STORM_ID);
  useEffect(() => {
    document.title = "Sif";
  }, []);

  return (
    <div className={`lp ${motion === "leave" ? "lp-leave" : motion === "enter" ? "lp-enter" : ""}`} role="dialog" aria-modal="false" aria-label="Sif">
      <div className="lp-scrim" aria-hidden="true" />
      <div className="lp-scroll">
        <section className="lp-hero">
          <p className="lp-kicker lp-rise" style={delay(0)}>
            SGX FX · Cloudy with a chance of margin calls
          </p>
          <h1 className="lp-title lp-rise" style={delay(1)} aria-label="Sif">
            Sif<span aria-hidden="true">.</span>
          </h1>
          <p className="lp-name lp-rise" style={delay(1)}>
            Named after Sif, whose farmers prayed for weather kind to their crops.
          </p>
          <p className="lp-lede lp-rise" style={delay(2)}>
            A storm defence for FX traders: the alarm sounds in the first minutes of a fast move, and two ships show what heeding it saved.
          </p>
          <div className="lp-cta lp-rise" style={delay(3)}>
            <button className="lp-btn primary lp-start" onClick={startExplorer} autoFocus>
              Start
              <kbd>Enter</kbd>
            </button>
          </div>

          {figures.length > 0 ? (
            <div className="lp-figs">
              <p className="lp-figs-head lp-rise" style={delay(4)}>
                Tested on {metrics?.month ?? "the test month"}, which tuning never saw
              </p>
              <div className="lp-figs-row">
                {figures.map((f, k) => (
                  <FigureCard key={f.key} f={f} k={k + 5} />
                ))}
              </div>
            </div>
          ) : (
            metrics === null && <p className="lp-quiet">The backtest's metrics are not in index.json yet, so no figures are shown.</p>
          )}
        </section>

        <div className="lp-sheet">
        <section className="lp-section lp-story">
          <SectionHead n="01">{story ? `The ${story.date} storm` : "The headline storm"}</SectionHead>
          {story ? (
            <div className="lp-story-grid">
              <div className="lp-story-text">
                {storySentences(story).map((t) => (
                  <p key={t}>{t}</p>
                ))}
                <p className="lp-tuning">
                  {story.month === "July"
                    ? "July was the tuning month, so this storm is in-sample. The numbers above are the out-of-sample test."
                    : "Read it with the test numbers above: only the test month is out of sample."}
                </p>
              </div>
              <Ledger s={story} />
            </div>
          ) : (
            <p className="lp-quiet">{story === undefined ? "Reading the bundle…" : "The headline bundle is not on this machine, so its story is not shown."}</p>
          )}
        </section>

        <section className="lp-section lp-how">
          <SectionHead n="02">How it works</SectionHead>
          <div className="lp-defences">
            {DEFENCES.map((d) => (
              <div className={`lp-defence ${d.cls}`} key={d.name}>
                <h3>{d.name}</h3>
                <p>{d.line}</p>
              </div>
            ))}
          </div>
          <div className="lp-crew">
            <span className="lp-crew-motto">Models read, code judges.</span>
            <span>
              Code decides every alarm. Models write the report and answer what-ifs, a different model family inspects them, and code checks every
              number they write.
            </span>
          </div>
          <ul className="lp-stack" aria-label="Data stack">
            {STACK.map((s) => (
              <li key={s.name}>
                <b>{s.name}</b>
                <span>{s.role}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="lp-section lp-honesty">
          <SectionHead n="03">What we do not claim</SectionHead>
          <ul>
            {HONESTY.map((h) => (
              <li key={h.b}>
                <b>{h.b}</b> {h.t}
              </li>
            ))}
          </ul>
          <a className="lp-more" href={README_HONESTY} target="_blank" rel="noreferrer">
            All the honesty notes in the README ↗
          </a>
        </section>

        {others.length > 0 && (
          <section className="lp-section lp-picker">
            <SectionHead n="04">Other storms</SectionHead>
            <div className="lp-storms">
              {others.map((s) => (
                <a
                  key={s.id}
                  className={`lp-storm ${s.id === NVDA_STORM_ID ? "nvda" : ""}`}
                  href={`?storm=${encodeURIComponent(s.id)}`}
                  onClick={inApp(() => openFromLanding(s.id))}
                  aria-busy={busy === s.id}
                >
                  <span className="lp-storm-sym">{s.symbol}</span>
                  <span className={`lp-storm-move ${s.down ? "down" : "up"}`}>{s.move}</span>
                  <span className="lp-storm-when">{s.when}</span>
                  <span className={`lp-storm-kind ${s.kind}`}>{s.kind}</span>
                </a>
              ))}
            </div>
          </section>
        )}

        <footer className="lp-foot">
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            github.com/kamil-shirinov/stormscore ↗
          </a>
          <span className="lp-keys" aria-label="Presenter keys">
            {KEYS.map(([k, what]) => (
              <span key={k}>
                <kbd>{k}</kbd> {what}
              </span>
            ))}
          </span>
          <button className="lp-close" onClick={closeLanding}>
            Open the replay <kbd>Esc</kbd>
          </button>
        </footer>
        </div>
      </div>
    </div>
  );
}
