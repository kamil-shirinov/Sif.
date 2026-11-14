// Browser side of the Survive parity check (see README.md here). Bundled with rolldown, run with node.
import { readFileSync } from "node:fs";
import { simulate, summarize } from "../../src/lib/survive.ts";

const cases = JSON.parse(readFileSync(process.argv[2], "utf8"));
let worst = 0, worstName = "", fails = 0;
const rows: string[] = [];
for (const c of cases) {
  const b: any = { ...c.bundle, t0: 1_780_000_000, step_s: 60, ships: { prepared: { start_equity_usd: 1_000_000 } }, events: [] };
  const sim = simulate(b, c.leverage, c.presses);
  const be = c.backend;
  let d = 0;
  for (let i = 0; i < b.n; i++) d = Math.max(d, Math.abs(sim.equity[i] - be.equity[i]));
  const cuts = sim.applied.filter((a) => a.kind === "cut").map((a) => a.i);
  const restores = sim.applied.filter((a) => a.kind === "restore").map((a) => a.i);
  const ok = d < 1e-4 && sim.marginCallI === be.mc && JSON.stringify(cuts) === JSON.stringify(be.cuts) && JSON.stringify(restores) === JSON.stringify(be.restores);
  if (!ok) { fails++; rows.push(`FAIL ${c.name}: d=${d} mc ${sim.marginCallI} vs ${be.mc} cuts ${cuts} vs ${be.cuts} restores ${restores} vs ${be.restores}`); }
  if (d > worst) { worst = d; worstName = c.name; }
}
console.log(rows.join("\n"));
console.log(`${cases.length} cases, ${fails} differ; largest equity difference ${worst.toExponential(2)} USD (${worstName})`);
// The reproducer through the end card's own comparison (summarize -> followed).
const rep = cases.find((c: any) => c.name.startsWith("reproducer"));
if (!rep) process.exit(0);
const b: any = { ...rep.bundle, t0: 1_780_000_000, step_s: 60, title: "x", storm: {}, ships: { prepared: { start_equity_usd: 1_000_000 } }, events: [{ i: 1, type: "alarm", text: "", move_ahead_pct: 0 }] };
const r = summarize(b, simulate(b, 20, []));
console.log("reproducer, summarize().followed:", JSON.stringify(r.followed));
