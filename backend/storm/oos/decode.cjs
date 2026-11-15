/* Re-decode retained .bi5 with the exact pinned package, without network access.
 * node decode.cjs PACKAGE_DIRECTORY MANIFEST_PATH
 * Emits volume-bearing, zero-volume-filtered CSVs alongside the originals.
 */
const fs = require('node:fs');
const path = require('node:path');

const [packageDir, manifestPath] = process.argv.slice(2);
const pkg = require(path.join(packageDir, 'package.json'));
if (pkg.name !== 'dukascopy-node' || pkg.version !== '1.46.4') {
  throw new Error('wrong pinned decoder');
}
const {processData} = require(packageDir);
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const root = path.dirname(manifestPath);

for (const window of manifest.windows) {
  for (const record of window.pairs) {
    if (record.status !== 'usable') throw new Error('correction expects a fully downloaded manifest');
    for (const side of ['bid', 'ask']) {
      const original = path.join(root, record.raw[side].path);
      const text = fs.readFileSync(original, 'utf8').trim();
      const timestamps = text.split('\n').slice(1).map(line => Number(line.split(',')[0]));
      const dates = [...new Set(timestamps.map(t => new Date(t).toISOString().slice(0,10)))].sort();
      const rows = [];
      for (const date of dates) {
        const [year, month, day] = date.split('-');
        const relative = ['datafeed', record.pair, year, String(Number(month)-1).padStart(2,'0'), day,
                          side.toUpperCase() + '_candles_min_1.bi5'];
        const artifact = path.join(root, 'feed-cache', ...relative);
        const decoded = processData({instrument: record.pair.toLowerCase(), requestedTimeframe: 'm1',
          bufferObjects: [{url: 'https://datafeed.dukascopy.com/' + relative.join('/'),
                           buffer: fs.readFileSync(artifact)}],
          priceType: side, volumes: true, volumeUnits: 'millions', ignoreFlats: true});
        for (const row of decoded) if (row.length === 6) rows.push(row);
      }
      rows.sort((a,b) => a[0]-b[0]);
      const target = original.replace(/\.csv$/, '_filtered.csv');
      if (fs.existsSync(target)) throw new Error('refusing to overwrite re-decoded CSV');
      fs.writeFileSync(target, 'timestamp,open,high,low,close,volume\n' +
                       rows.map(row => row.join(',')).join('\n') + '\n');
      console.log(window.id, record.pair, side, 'retained', rows.length, 'of', timestamps.length);
    }
  }
}
