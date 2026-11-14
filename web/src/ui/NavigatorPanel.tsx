import { useEffect, useRef, useState, type FormEvent } from "react";
import { useApp } from "../state/app";
import { ApiError, askNavigator, NAVIGATOR_MAX_QUESTION, type NavigatorAnswer } from "../lib/api";
import { openStorm, sailScenario } from "../lib/session";
import { DEFAULT_STORM_ID } from "../lib/loadBundle";
import { InspectorLine, VerifiedBadge } from "./ReportPanel";

/** Shown only when /api/health says navigator is true. */
export function NavigatorPanel() {
  const available = useApp((s) => s.health?.navigator === true);
  return available ? <NavigatorBox /> : null;
}

function NavigatorBox() {
  const bundle = useApp((s) => s.bundle);
  const baseStormId = useApp((s) => s.baseStormId);
  const index = useApp((s) => s.index);
  const [open, setOpen] = useState(true);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<NavigatorAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ctl = useRef<AbortController | null>(null);
  const box = useRef<HTMLDivElement>(null);

  // The answer is about one storm: drop it when another storm is chosen (a scenario keeps its base storm).
  useEffect(() => {
    ctl.current?.abort();
    setAnswer(null);
    setError(null);
    setBusy(false);
  }, [baseStormId]);
  useEffect(() => () => ctl.current?.abort(), []);
  // The column scrolls on short screens: bring a new answer into view.
  useEffect(() => {
    if (answer || error) box.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [answer, error]);

  const stormId = baseStormId ?? bundle?.storm_id ?? DEFAULT_STORM_ID;
  const sailing = answer?.scenario !== null && answer?.scenario !== undefined && bundle === answer.scenario;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || busy) return;
    ctl.current?.abort();
    const c = new AbortController();
    ctl.current = c;
    setBusy(true);
    setError(null);
    try {
      const a = await askNavigator(q, stormId, c.signal);
      if (c.signal.aborted) return;
      setAnswer(a);
    } catch (err) {
      if (c.signal.aborted) return;
      setAnswer(null);
      setError(err instanceof ApiError ? err.message : "The navigator did not answer.");
    } finally {
      if (ctl.current === c) setBusy(false);
    }
  };

  const backToStorm = () => void openStorm(stormId, index?.storms.find((s) => s.storm_id === stormId)?.file);

  return (
    <div className="panel stack-item navigator" ref={box}>
      <button className="panel-head panel-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span>Ask the navigator</span>
        <span className="toggle-chevron" aria-hidden="true">
          {open ? "▴" : "▾"}
        </span>
      </button>
      {open && (
        <>
          <form className="nav-form" onSubmit={submit}>
            <input
              type="text"
              value={question}
              maxLength={NAVIGATOR_MAX_QUESTION}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about this storm…"
              aria-label="Question for the navigator"
              disabled={busy}
            />
            <button type="submit" disabled={busy || question.trim() === ""}>
              {busy ? "…" : "Ask"}
            </button>
          </form>
          {error && <div className="nav-error">{error}</div>}
          {answer && (
            <div className="nav-answer">
              <div className="badges">
                <VerifiedBadge verified={answer.verified} unverified={answer.unverified} />
              </div>
              <div className="report-text">
                {answer.answer
                  .split(/\n+/)
                  .filter((p) => p.trim())
                  .map((p, k) => (
                    <p key={k}>{p}</p>
                  ))}
              </div>
              {answer.inspector && <InspectorLine inspector={answer.inspector} />}
              {answer.scenario && !sailing && (
                <button className="sail" onClick={() => answer.scenario && sailScenario(answer.scenario)}>
                  Sail this scenario
                </button>
              )}
              {answer.scenario && sailing && (
                <div className="nav-sailing">
                  <span>Sailing: {answer.scenario.title}</span>
                  <button className="link" onClick={backToStorm}>
                    Back to the recorded storm
                  </button>
                </div>
              )}
              {answer.scenarioError && <div className="nav-error">The scenario could not be loaded: {answer.scenarioError}</div>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
