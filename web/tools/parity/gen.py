"""Parity cases: the backend's simulate_book / simulate_stock on the same prices the browser sees."""
import json, sys
import numpy as np
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / 'backend'))
from storm.exposure import Quotes, simulate_book, book_for
from storm.equity import simulate_stock

rng = np.random.default_rng(7)
cases = []

def fx_path(pair, n=240, drop=-0.03):
    p0 = {'USDJPY': 158.0, 'EURUSD': 1.085, 'USDSGD': 1.345}[pair]
    r = rng.normal(0, 0.0004, n)
    r[120:150] += drop / 30           # the storm
    r[150:200] -= drop / 100          # partial recovery
    mid = p0 * np.exp(np.cumsum(r))
    mid = np.round(mid, 5 if pair != 'USDJPY' else 3)
    gap = rng.normal(0, 0.00015, n)   # opens differ from the previous close
    opn = np.round(np.concatenate([[mid[0]], mid[:-1]]) * (1 + gap), 5 if pair != 'USDJPY' else 3)
    opn[0] = mid[0]
    spread = np.round(rng.uniform(0.2, 2.5, n) * (1 + 3 * (np.arange(n) >= 120) * (np.arange(n) < 150)), 3)
    return mid, opn, spread

def quotes_from(mid, opn, spread):
    # The browser's quote model: close spread = the bar's spread_bp, open spread = the previous bar's.
    half = spread / 2e4
    oh = np.concatenate([half[:1], half[:-1]])
    return Quotes(mid, opn, opn * (1 - oh), opn * (1 + oh), mid * (1 - half), mid * (1 + half), np.ones(len(mid), bool))

def fx_case(name, pair, mid, opn, spread, L, presses, source='sgx'):
    book = book_for(pair, notional_usd=L * 1_000_000.0)
    path = simulate_book({pair: quotes_from(mid, opn, spread)}, book, [(i + 1, pair, k) for i, k in presses])
    cases.append({'name': name, 'bundle': {'symbol': pair, 'asset_class': 'fx', 'source': source, 'n': len(mid),
                  'series': {'mid': mid.tolist(), 'open': opn.tolist(), 'spread_bp': spread.tolist()}},
                  'leverage': L, 'presses': [{'i': i, 'kind': k} for i, k in presses],
                  'backend': {'equity': path.equity.tolist(), 'mc': path.margin_call_i,
                              'cuts': [i for i, _ in path.cuts], 'restores': [i for i, _ in path.restores]}})

ACTIONS = {'hold': [], 'cut': [(124, 'cut')], 'cut+restore': [(124, 'cut'), (170, 'restore')],
           'two cuts': [(110, 'cut'), (118, 'restore'), (126, 'cut')]}
for pair, drop in (('USDJPY', -0.035), ('EURUSD', 0.035), ('USDSGD', -0.03)):
    mid, opn, spread = fx_path(pair, drop=drop)
    for L in (1, 5, 10, 20, 30):
        for an, acts in ACTIONS.items():
            fx_case(f'{pair} {L}x {an}', pair, mid, opn, spread, L, acts)

# Equity: Yahoo bars (no quotes), a closed night in the middle.
n = 300
r = rng.normal(0, 0.0012, n); r[200:230] -= 0.004
price = np.round(180 * np.exp(np.cumsum(r)), 2)
traded = np.ones(n, bool); traded[100:160] = False
price[100:160] = price[99]
opn = np.round(np.concatenate([[price[0]], price[:-1]]) * (1 + rng.normal(0, 0.0005, n)), 2); opn[0] = price[0]
opn[160] = round(price[159] * 0.985, 2)   # gap at the reopen
opn_b = np.where(traded, opn, price)
for L in (1, 2, 4, 5, 6):
    for an, acts in {'hold': [], 'cut': [(205, 'cut')], 'cut+restore': [(205, 'cut'), (250, 'restore')],
                     'cut before close': [(99, 'cut'), (180, 'restore')]}.items():
        book = {'symbol': 'NVDA', 'equity_usd': 1_000_000.0, 'position_usd': L * 1_000_000.0, 'maintenance_margin': 0.15, 'cut_fraction': 0.75}
        path = simulate_stock(price, book, [(i + 1, 'NVDA', k) for i, k in acts], open_price=opn_b, traded=traded)
        cases.append({'name': f'NVDA {L}x {an}', 'bundle': {'symbol': 'NVDA', 'asset_class': 'equity', 'source': 'yahoo', 'n': n,
                      'series': {'mid': price.tolist(), 'open': opn.tolist(), 'spread_bp': [0.0] * n, 'market_open': traded.astype(int).tolist()}},
                      'leverage': L, 'presses': [{'i': i, 'kind': k} for i, k in acts],
                      'backend': {'equity': path.equity.tolist(), 'mc': path.margin_call_i,
                                  'cuts': [i for i, _ in path.cuts], 'restores': [i for i, _ in path.restores]}})

# The audit's reproducer: USDJPY closes [100, 97.5, 99, 99], $1m, 20x, alarm at frame 1 (no quotes: from_mid).
mid = np.array([100, 97.5, 99, 99.0]); opn = np.array([100, 100, 97.5, 99.0]); sp = np.zeros(4)
fx_case('reproducer USDJPY 20x alarm@1', 'USDJPY', mid, opn, sp, 20, [(1, 'cut')], source='synthetic')
# Open gap: breached at frame 2's open, back above the line by its close: a margin call at the open, before any fill.
mid = np.array([100, 100, 99.6, 99.6, 99.6]); opn = np.array([100, 100, 97.5, 99.6, 99.6]); sp = np.full(5, 0.8)
fx_case('open gap USDJPY 20x, cut pressed at 1', 'USDJPY', mid, opn, sp, 20, [(1, 'cut')])
fx_case('open gap USDJPY 20x, hold', 'USDJPY', mid, opn, sp, 20, [])
# Refused restore: cut, the price keeps falling, a restore would put the book under the line.
mid = np.array([100, 99.5, 97.5, 96.6, 96.5, 96.5]); opn = np.concatenate([[100], mid[:-1]]); sp = np.full(6, 1.0)
fx_case('refused restore USDJPY 30x', 'USDJPY', mid, opn, sp, 30, [(0, 'cut'), (3, 'restore')])
mid = np.array([1.08, 1.083, 1.1, 1.117, 1.118, 1.118]); opn = np.concatenate([[1.08], mid[:-1]]); sp = np.full(6, 1.2)
fx_case('refused restore EURUSD 30x', 'EURUSD', mid, opn, sp, 30, [(0, 'cut'), (3, 'restore')])
mid = np.array([100, 97.5, 99, 99.0]); q = Quotes.from_mid(mid)
p = simulate_book({'USDJPY': q}, book_for('USDJPY', 20e6), [(2, 'USDJPY', 'cut')])
print('reproducer, backend from_mid:', p.margin_call_i, round(p.equity[-1], 2), p.cuts)
json.dump(cases, open('cases.json', 'w'))
print(len(cases), 'cases')
