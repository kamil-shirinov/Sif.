/* Acquisition-only HTTPS transport for the pinned decoder's fetch(url).
 * Node's native fetch connects with a 10s limit; this feed needed >10s.
 * No changes to requests, responses, candles or the decoder. Core HTTPS
 * verifies TLS normally. The downloader owns the three bounded retries.
 */
const https = require('node:https');
const fs = require('node:fs/promises');
const path = require('node:path');

globalThis.fetch = async function dukascopyFetch(input) {
  const url = new URL(input);
  if (url.protocol !== 'https:' || url.hostname !== 'datafeed.dukascopy.com' ||
      !/^\/datafeed\/[A-Z]{6}\/\d{4}\/\d{2}\/\d{2}\/(BID|ASK)_candles_min_1\.bi5$/.test(url.pathname)) {
    throw new Error('OOS transport accepts only registered-feed minute candle URLs');
  }
  return new Promise((resolve, reject) => {
    const request = https.get(url, { timeout: 60_000 }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('error', reject);
      response.on('end', async () => {
        try {
          const body = Buffer.concat(chunks);
          if (response.statusCode === 200) {
            const target = path.join(process.env.OOS_FEED_CACHE, ...url.pathname.split('/').filter(Boolean));
            await fs.mkdir(path.dirname(target), { recursive: true });
            await fs.writeFile(target, body);
          }
          resolve(new Response(body, { status: response.statusCode, headers: response.headers }));
        } catch (error) { reject(error); }
      });
    });
    request.on('timeout', () => request.destroy(new Error('Dukascopy HTTPS transport timed out after 60000ms')));
    request.on('error', reject);
  });
};
