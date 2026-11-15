import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { Bundle } from "../../types/bundle";
import { tutorialCards, type TutorialCard } from "./tutorialCards";

/** Survive's first-run tutorial: three cards over the sea, skippable (Skip, Esc), arrow keys step through. */
export function Tutorial({ bundle, onClose }: { bundle: Bundle; onClose: () => void }) {
  const cards = useMemo(() => tutorialCards(bundle), [bundle]);
  const [k, setK] = useState(0);
  const primary = useRef<HTMLButtonElement>(null);
  const last = k === cards.length - 1;
  const card = cards[k];

  useEffect(() => {
    primary.current?.focus();
  }, [k]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation(); // Esc closes the cards, not the presenter's view
        onClose();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        setK((x) => Math.min(cards.length - 1, x + 1));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setK((x) => Math.max(0, x - 1));
      } else if (e.key === " " || e.key === "c" || e.key === "C" || e.key === "r" || e.key === "R") {
        // Space, C and R belong to the game: not while the cards are up.
        e.stopPropagation();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [cards.length, onClose]);

  return createPortal(
    <div className="tut-wrap">
      <div className="tut-card" role="dialog" aria-modal="true" aria-labelledby="tut-title" aria-describedby="tut-text">
        <div className="tut-head">
          <span className="tut-step">
            How to play · {k + 1} of {cards.length}
          </span>
          <button className="tut-skip" onClick={onClose}>
            Skip
          </button>
        </div>
        <TutorialArt kind={card.key} />
        <h2 id="tut-title" className="tut-title">
          {card.title}
        </h2>
        <p id="tut-text" className="tut-text">
          {card.text}
        </p>
        <div className="tut-foot">
          <div className="tut-dots" aria-hidden="true">
            {cards.map((c, j) => (
              <span key={c.key} className={j === k ? "on" : ""} />
            ))}
          </div>
          {k > 0 && (
            <button className="ghost-btn" onClick={() => setK(k - 1)}>
              Back
            </button>
          )}
          <button ref={primary} className="sail-btn tut-next" onClick={() => (last ? onClose() : setK(k + 1))}>
            {last ? "Got it" : "Next"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** A small drawing per card: a ship and its cargo, the red line, a cut. Decorative only. */
function TutorialArt({ kind }: { kind: TutorialCard["key"] }) {
  const sea = <path d="M0 62 Q 20 56 40 62 T 80 62 T 120 62 T 160 62 T 200 62 V 80 H 0 Z" fill="#1d4f73" />;
  const hull = <path d="M62 50 H 138 L 128 64 H 72 Z" fill="#c9d6e2" />;
  const crate = (x: number, y: number, c: string, key: string) => <rect key={key} x={x} y={y} width="11" height="9" rx="1.5" fill={c} />;
  const colors = ["#c47f36", "#3f7fc4", "#5aa168", "#c14b4b", "#8b6cc4", "#c4b13f"];
  let deck: ReactNode[] = [];
  if (kind === "leverage") {
    for (let row = 0; row < 3; row++) for (let col = 0; col < 5; col++) deck.push(crate(70 + col * 12, 40 - row * 10, colors[(row * 5 + col) % 6], `${row}-${col}`));
  } else if (kind === "line") {
    for (let col = 0; col < 5; col++) deck.push(crate(70 + col * 12, 40, colors[col % 6], `${col}`));
  } else {
    deck = [crate(94, 40, colors[0], "kept")];
  }
  return (
    <svg className="tut-art" viewBox="0 0 200 80" aria-hidden="true">
      {kind === "line" && (
        <>
          <line x1="0" y1="70" x2="200" y2="70" stroke="#ff6b66" strokeWidth="2" strokeDasharray="6 4" />
          <text x="196" y="77" textAnchor="end" fill="#ff8a84" fontSize="7">
            margin call
          </text>
        </>
      )}
      {sea}
      {hull}
      <line x1="100" y1="50" x2="100" y2="14" stroke="#c9d6e2" strokeWidth="2" />
      {deck}
      {kind === "cut" && (
        <>
          {crate(146, 30, colors[1], "f1")}
          {crate(160, 44, colors[2], "f2")}
          {crate(150, 56, colors[3], "f3")}
          <path d="M120 38 Q 140 22 150 28" fill="none" stroke="#f5a623" strokeWidth="1.5" strokeDasharray="3 3" />
        </>
      )}
      {kind === "leverage" && (
        <text x="30" y="30" textAnchor="middle" fill="#7cc4ff" fontSize="12" fontWeight="700">
          ×L
        </text>
      )}
    </svg>
  );
}
