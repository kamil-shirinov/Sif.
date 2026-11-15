# Survive parity check

Checks that `src/lib/survive.ts` (the browser's book) gives the same equity, margin-call frame, cut fills and restore fills as the backend's `storm.exposure.simulate_book` (FX) and `storm.equity.simulate_stock` (equities), on the same prices.

```bash
cd web/tools/parity
python gen.py            # writes cases.json from the backend (needs backend/requirements.txt installed)
../../node_modules/.bin/rolldown harness.ts --file harness.mjs --platform node --format esm
node harness.mjs cases.json
python gap.py && node harness.mjs gap.json   # the by-design gap: a real open spread that differs from the estimate
```

The backend is fed the quote model the browser uses (open bid/ask = open mid -/+ half the previous bar's spread_bp, close bid/ask = mid -/+ half the bar's spread_bp), because the bundle carries no open quotes. `gap.py` feeds it a different open spread instead, to bound that difference. Generated files (`*.json`, `harness.mjs`) are not committed.
