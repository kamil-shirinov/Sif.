/* Decode only saved round-two bodies. No network, interpolation or outlier filter.
 * node decode2.cjs PACKAGE_DIRECTORY DATA_ROOT
 */
const fs=require('node:fs'); const path=require('node:path');
const [packageDir,root]=process.argv.slice(2);
const pkg=require(path.join(packageDir,'package.json'));
if(pkg.name!=='dukascopy-node'||pkg.version!=='1.46.4') throw new Error('wrong frozen decoder');
const {processData}=require(packageDir);
const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
const records=[];
for(const month of manifest.months){
 if(!manifest.selected_months.includes(month.id)) continue;
 for(const rec of month.pairs){
  const row={month:month.id,pair:rec.pair,status:'decoded',reason:null,sides:{}};
  try{
   for(const side of ['bid','ask']){
    const rows=[]; let saved=0,missing=0;
    for(let d=new Date(month.download_start+'T00:00:00Z'); d<new Date(month.end_exclusive+'T00:00:00Z'); d.setUTCDate(d.getUTCDate()+1)){
     const relative=['datafeed',rec.pair,String(d.getUTCFullYear()),String(d.getUTCMonth()).padStart(2,'0'),String(d.getUTCDate()).padStart(2,'0'),side.toUpperCase()+'_candles_min_1.bi5'];
     const artifact=path.join(root,'feed-cache',...relative);
     if(!fs.existsSync(artifact)){missing++;continue;}
     saved++;
     const result=processData({instrument:rec.pair.toLowerCase(),requestedTimeframe:'m1',
       bufferObjects:[{url:'https://datafeed.dukascopy.com/'+relative.join('/'),buffer:fs.readFileSync(artifact)}],
       priceType:side,volumes:true,volumeUnits:'millions',ignoreFlats:true});
     for(const value of result) if(value.length===6) rows.push(value);
    }
    rows.sort((a,b)=>a[0]-b[0]);
    const folder=path.join(root,month.id,'decoded');fs.mkdirSync(folder,{recursive:true});
    const target=path.join(folder,rec.pair+'_'+side+'.csv');
    if(fs.existsSync(target)) throw new Error('refusing a second decode');
    fs.writeFileSync(target,'timestamp,open,high,low,close,volume\n'+rows.map(r=>r.join(',')).join('\n')+(rows.length?'\n':''));
    row.sides[side]={path:path.relative(root,target),saved_daily_artifacts:saved,missing_daily_artifacts:missing,rows:rows.length};
   }
  }catch(error){row.status='unusable';row.reason=error.message;}
  records.push(row);
 }
}
fs.writeFileSync(path.join(root,'decoded-manifest.json'),JSON.stringify(records,null,2)+'\n');
