// Survive's end card in words: what happened, what the alarm-follower did, one lesson, and a line to share.
// Pure code (tested by survive.test.mjs). Every number comes from the run's RunResult (lib/survive.ts summarize) and
// the bundle's clock; the words around them are fixed templates.

import type { Bundle } from "../../types/bundle";
import { fmtClock, fmtPct, fmtUsd } from "../../lib/format";
import { CUT_FRACTION, type RunResult } from "../../lib/survive";

const pct = (x: number) => `${Math.abs(x).toFixed(1)}%`;
const clock = (b: Pick<Bundle, "t0" | "step_s">, i: number) => `${fmtClock(b.t0 + i * b.step_s)} UTC`;
const share = Math.round(CUT_FRACTION * 100);

/** One or two sentences: how the player's own run went. */
export function whatHappened(b: Bundle, r: RunResult): string {
  const L = r.leverage;
  const cut =
    r.cuts > 0 && r.firstCutI !== null ? ` You cut ${share}% of the cargo at ${clock(b, r.firstCutI)}.` : r.sunk ? " You never cut." : " You kept the whole cargo aboard.";
  if (r.sunk && r.marginCallI !== null) {
    return `At ${L}x the price moved ${pct(r.worstAdversePct)} against you and the broker closed your trade at ${clock(b, r.marginCallI)}. You kept ${fmtUsd(r.score)} of your ${fmtUsd(r.startEquity, true)}.${cut}`;
  }
  const worst =
    r.worstAdversePct > 0
      ? ` At the worst moment, ${clock(b, r.worstAdverseI)}, the price was ${pct(r.worstAdversePct)} against you.`
      : " The price never went against you.";
  return `You rode out the storm at ${L}x and came home with ${fmtUsd(r.score)} (${fmtPct(r.changePct)}).${worst}${cut}`;
}

/** What the ship that followed the alarm did (cut 75% at the alarm, restored at the all-clear), against the player. */
export function alarmFollower(b: Bundle, r: RunResult): string {
  const F = r.followed;
  if (!F || r.alarmI === null) return "This storm raised no alarm, so the alarm-follower had nothing to act on.";
  const heard = `The alarm sounded at ${clock(b, r.alarmI)}.`;
  if (F.cutI === null) {
    return `${heard} At ${r.leverage}x the margin call came before the alarm-follower's cut could fill at the next minute's open.`;
  }
  const did = `The alarm-follower cut ${share}% at the ${clock(b, F.cutI)} open`;
  if (F.sunk && F.marginCallI !== null) return `${heard} ${did}, but at ${r.leverage}x even that ship went down at ${clock(b, F.marginCallI)}.`;
  const end = Math.max(0, F.equity);
  const diff = end - r.score;
  const vs = Math.abs(diff) < 0.5 ? "the same as you" : diff > 0 ? `${fmtUsd(diff)} more than you` : `${fmtUsd(-diff)} less than you`;
  return `${heard} ${did} and came home with ${fmtUsd(end)}, ${vs}.`;
}

/** The one lesson of this run, in a sentence. */
export function lessonFor(b: Bundle, r: RunResult): string {
  const L = r.leverage;
  const F = r.followed;
  const callMove = pct(r.line.movePct);
  if (r.sunk) {
    if (F && !F.sunk && F.cutI !== null) {
      return `When the alarm sounds, lighten the ship first and think second: here a cut at the alarm would have kept ${fmtUsd(Math.max(0, F.equity))} afloat.`;
    }
    if (F) return `At ${L}x a ${callMove} move against you sinks the ship faster than any alarm can help; less leverage buys you time to act.`;
    return `At ${L}x a ${callMove} move against you was enough to sink you: choose leverage for the worst move you can survive, not the best one you hope for.`;
  }
  if (r.cuts > 0) {
    if (r.held.sunk && r.held.marginCallI !== null) return `Your cut saved the ship: holding everything would have sunk at ${clock(b, r.held.marginCallI)}.`;
    const diff = r.score - Math.max(0, r.held.equity);
    return diff >= 0
      ? `Cutting when the sea turned kept ${fmtUsd(diff)} more than holding everything.`
      : `A cut is insurance: this time it cost ${fmtUsd(-diff)} against holding, but it caps what the next storm can take.`;
  }
  if (r.worstAdversePct <= 0) {
    return `This storm blew your way, but leverage works both ways: at ${L}x a ${callMove} move against you would have sunk you.`;
  }
  if (r.minBuffer < 0.3) {
    return `You made it, but your safety margin fell to ${Math.round(r.minBuffer * 100)}% of your money: at ${L}x a slightly bigger move would have sunk you.`;
  }
  return `At ${L}x you rode out a ${pct(r.worstAdversePct)} move against you with room to spare: your leverage decides how much room you have.`;
}

/** A plain-text line to paste anywhere, e.g. "Sif Survive · USDJPY, 30 July 2026 (Hard) · 10x · Land ho! $1,034,000 (+3.4%) · alarm-follower $1,012,000". */
export function shareLine(b: Bundle, r: RunResult, difficulty: string | null, url?: string): string {
  const parts = [
    "Sif Survive",
    `${b.title}${difficulty ? ` (${difficulty})` : ""}${r.scenario ? " what-if" : ""}`,
    `${r.leverage}x`,
    `${r.sunk ? "Sunk" : "Land ho!"} ${fmtUsd(r.score)} (${fmtPct(r.changePct)})`,
  ];
  if (r.followed) parts.push(`alarm-follower ${fmtUsd(Math.max(0, r.followed.equity))}`);
  if (url) parts.push(url);
  return parts.join(" · ");
}

/** The link a share line carries: this page, opening Survive on this storm. */
export function shareUrl(href: string, stormId: string): string {
  try {
    const u = new URL(href);
    u.search = "";
    u.hash = "";
    u.searchParams.set("mode", "survive");
    u.searchParams.set("storm", stormId);
    return u.toString();
  } catch {
    return "";
  }
}
