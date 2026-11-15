/* Acquisition-only transport for the pinned decoder's fetch(url).
 * See both dated transport amendments. Registration 2 follows the feed's current HTTPS endpoint; see its
 * dated HTTPS amendment. No changes
 * to artifact paths, response bodies, candles or the pinned decoder.
 * The downloader owns the three bounded retries.
 */
const http = require('node:https');
const fs = require('node:fs/promises');
const path = require('node:path');
const sync = require('node:fs');
const exhausted = new Set(process.env.OOS_BLOCKED_URLS ?
  JSON.parse(sync.readFileSync(process.env.OOS_BLOCKED_URLS, 'utf8')) : []);

globalThis.fetch = async function dukascopyFetch(input) {
  const url = new URL(input);
  if (url.protocol !== 'https:' || url.hostname !== 'datafeed.dukascopy.com' ||
      !/^\/datafeed\/[A-Z]{6}\/\d{4}\/\d{2}\/\d{2}\/(BID|ASK)_candles_min_1\.bi5$/.test(url.pathname)) {
    throw new Error('OOS transport accepts only registered-feed minute candle URLs');
  }
  const target = path.join(process.env.OOS_FEED_CACHE, ...url.pathname.split('/').filter(Boolean));
  if (sync.existsSync(target)) {
    const body = await fs.readFile(target);
    await fs.appendFile(process.env.OOS_TRANSPORT_LOG,
      JSON.stringify({utc:new Date().toISOString(),url:url.href,status:200,bytes:body.length,cache:true,network:false})+'\n');
    return new Response(body,{status:200,headers:{'content-length':String(body.length)}});
  }
  if (exhausted.has(url.href)) {
    await fs.appendFile(process.env.OOS_TRANSPORT_LOG,
      JSON.stringify({utc:new Date().toISOString(),url:url.href,status:503,bytes:0,exhausted_previous_pass:true,network:false})+'\n');
    return new Response('',{status:503});
  }
  return new Promise((resolve, reject) => {
    const request = http.get(url, { timeout: 60_000 }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('error', reject);
      response.on('end', async () => {
        try {
          const body = Buffer.concat(chunks);
          if (process.env.OOS_TRANSPORT_LOG) {
            await fs.appendFile(process.env.OOS_TRANSPORT_LOG,
              JSON.stringify({utc: new Date().toISOString(), url: url.href,
                              status: response.statusCode, bytes: body.length}) + '\n');
          }
          if (response.statusCode === 200) {
            await fs.mkdir(path.dirname(target), { recursive: true });
            await fs.writeFile(target, body);
          }
          resolve(new Response(body, { status: response.statusCode, headers: response.headers }));
        } catch (error) { reject(error); }
      });
    });
    request.on('timeout', () => request.destroy(new Error('Dukascopy HTTPS transport timed out after 60000ms')));
    request.on('error', async error => {
      if(process.env.OOS_TRANSPORT_LOG) await fs.appendFile(process.env.OOS_TRANSPORT_LOG,
        JSON.stringify({utc:new Date().toISOString(),url:url.href,error:error.message,network:true})+'\n');
      reject(error);
    });
  });
};
