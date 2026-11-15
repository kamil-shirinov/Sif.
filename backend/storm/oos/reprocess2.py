"""Final conversion from all successful saved bodies; no new data requests or scoring."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

import pandas as pd

from .acquire import OHLC, read_side
from .acquire2 import convert_month
from .protocol import DOCS, sha256
from .protocol2 import DATA2, check_frozen2


def convert_warmup(bid, ask, output):
    b,a=read_side(bid),read_side(ask)
    f=b.join(a,how='inner',lsuffix='_bid',rsuffix='_ask')
    if ((f.index<pd.Timestamp('2024-12-27',tz='UTC'))|(f.index>=pd.Timestamp('2025-01-01',tz='UTC'))).any():
        raise ValueError('warm-up outside registered December interval')
    if len(f)<720: raise ValueError(f'insufficient initial warm-up: {len(f)} < 720')
    if (f[['open_ask','close_ask']].to_numpy()<f[['open_bid','close_bid']].to_numpy()).any():
        raise ValueError('negative warm-up open/close spread')
    for col in OHLC: f[col+'_mid']=(f[col+'_bid']+f[col+'_ask'])/2
    f.insert(0,'settlement_date',f.index.tz_localize(None).normalize())
    output.parent.mkdir(parents=True,exist_ok=True)
    f.reset_index().to_parquet(output,index=False)
    return {'status':'usable','path':str(output.relative_to(DATA2)),'sha256':sha256(output),'rows':len(f)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package-dir',type=Path,required=True)
    args=ap.parse_args()
    spec=check_frozen2()
    if sha256(args.package_dir/'dist/cli/index.js') != spec['downloader']['cli_sha256']:
        raise SystemExit('registered decoder/CLI source changed')
    if (DOCS/'run-2-started.json').exists() or (DOCS/'results-2.json').exists():
        raise SystemExit('a primary detector run already started; conversion refused')
    old=DATA2/'manifest-before-final-decode.json'
    if old.exists(): raise SystemExit('final conversion already attempted')
    shutil.copyfile(DATA2/'manifest.json',old)
    with (DATA2/'final-decode.log').open('w') as log:
        subprocess.run(['node',str(Path(__file__).with_name('decode2.cjs')),str(args.package_dir),str(DATA2)],
                       stdout=log,stderr=subprocess.STDOUT,check=True)
    decoded={(r['month'],r['pair']):r for r in json.loads((DATA2/'decoded-manifest.json').read_text())}
    manifest=json.loads(old.read_text())
    checked_rows=0
    for window in manifest['months']:
        for record in window['pairs']:
            key=(window['id'],record['pair'])
            if key not in decoded: continue
            rec=decoded[key]
            record['acquisition_status']=record['status']
            record['acquisition_reason']=record['reason']
            record['initial_raw']=record['raw']
            record['raw']={}
            if window['id']=='2025-01':
                try:
                    if rec['status']!='decoded': raise ValueError('saved-body decode failed')
                    warm=DATA2/window['id']/'processed'/f"{record['pair']}_WARMUP.parquet"
                    record['warmup']=convert_warmup(DATA2/rec['sides']['bid']['warmup_path'],
                        DATA2/rec['sides']['ask']['warmup_path'],warm)
                except (ValueError,KeyError,OSError) as exc:
                    record['warmup']={'status':'unusable','reason':str(exc)}
            try:
                if rec['status']!='decoded': raise ValueError('saved-body decoder: '+rec['reason'])
                for side,item in rec['sides'].items():
                    path=DATA2/item['path']
                    record['raw'][side]={'path':item['path'],'sha256':sha256(path)}
                    prior=DATA2/window['id']/'raw'/f"{record['pair']}_{side}.csv"
                    if prior.exists() and prior.stat().st_size:
                        previous=pd.read_csv(prior).set_index('timestamp')[list(OHLC)]
                        current=pd.read_csv(path).set_index('timestamp')[list(OHLC)]
                        overlap=previous.index.intersection(current.index)
                        if len(overlap):
                            pd.testing.assert_frame_equal(previous.loc[overlap],current.loc[overlap],check_exact=True)
                        checked_rows+=len(overlap)
                out=DATA2/window['id']/'processed'/f"{record['pair']}_SPOT.parquet"
                if out.exists():
                    prior=out.parent.with_name('initial-processed')/out.name
                    prior.parent.mkdir(parents=True,exist_ok=True)
                    shutil.move(str(out),str(prior))
                record['quality']=convert_month(DATA2/rec['sides']['bid']['path'],DATA2/rec['sides']['ask']['path'],window,out)
                record['quality']['saved_daily_artifacts']={s:r['saved_daily_artifacts'] for s,r in rec['sides'].items()}
                record['quality']['missing_daily_artifacts']={s:r['missing_daily_artifacts'] for s,r in rec['sides'].items()}
                record.update(status='usable',reason=None,parquet={'path':str(out.relative_to(DATA2)),'sha256':sha256(out)})
            except (ValueError,KeyError,OSError) as exc:
                record.update(status='unusable',reason=str(exc))
                record.pop('parquet',None)
                if hasattr(exc,'quality'): record['quality']=exc.quality
                else: record.pop('quality',None)
            print(window['id'],record['pair'],record['status'],record['reason'] or '',flush=True)
    manifest['final_conversion']={'utc':pd.Timestamp.now(tz='UTC').isoformat(),'network_requests':0,
        'cli_overlap_ohlc_rows_verified_exact':checked_rows,
        'decoder_api_sha256':sha256(args.package_dir/'dist/index.js'),
        'npm_lock_sha256':sha256(args.package_dir.parent.parent/'package-lock.json'),
        'node_version':subprocess.check_output(['node','--version'],text=True).strip(),
        'note_sha256':sha256(DOCS/'acquisition-notes-2.md')}
    (DATA2/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
