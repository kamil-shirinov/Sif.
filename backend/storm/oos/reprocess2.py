"""Final conversion from all successful saved bodies; no new data requests or scoring."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

import pandas as pd

from .acquire import OHLC
from .acquire2 import convert_month
from .protocol import DOCS, sha256
from .protocol2 import DATA2, check_frozen2


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package-dir',type=Path,required=True)
    args=ap.parse_args()
    check_frozen2()
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
                record.pop('quality',None)
            print(window['id'],record['pair'],record['status'],record['reason'] or '',flush=True)
    manifest['final_conversion']={'utc':pd.Timestamp.now(tz='UTC').isoformat(),'network_requests':0,
        'cli_overlap_ohlc_rows_verified_exact':checked_rows,
        'decoder_api_sha256':sha256(args.package_dir/'dist/index.js'),
        'note_sha256':sha256(DOCS/'acquisition-notes-2.md')}
    (DATA2/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
