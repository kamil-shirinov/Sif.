# By design: the bundle has no open bid/ask. Feed the backend open quotes whose spread differs from the browser's
# estimate (the bar's own close spread instead of the previous bar's) to bound the effect of a different real open spread.
import json, sys, numpy as np
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / 'backend'))
from storm.exposure import Quotes, simulate_book, book_for
c = json.load(open('cases.json'))
out = []
for x in c:
    if x['bundle']['asset_class'] != 'fx' or x['name'].startswith('reproducer'): continue
    s = x['bundle']['series']; mid = np.array(s['mid']); opn = np.array(s['open']); sp = np.array(s['spread_bp'])
    sp_o = sp / 2e4; h = sp / 2e4  # the other choice: the open spread equal to the bar's own close spread
    q = Quotes(mid, opn, opn * (1 - sp_o), opn * (1 + sp_o), mid * (1 - h), mid * (1 + h), np.ones(len(mid), bool))
    pair = x['bundle']['symbol']
    p = simulate_book({pair: q}, book_for(pair, x['leverage'] * 1e6), [(a['i'] + 1, pair, a['kind']) for a in x['presses']])
    x['backend'] = {'equity': p.equity.tolist(), 'mc': p.margin_call_i, 'cuts': [i for i, _ in p.cuts], 'restores': [i for i, _ in p.restores]}
    out.append(x)
json.dump(out, open('gap.json', 'w'))
