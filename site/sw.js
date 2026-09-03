/* Service worker: the page opens with no signal, and the map tiles and photos
   you've already looked at stay available.

   - The page itself is network-first with a short timeout, falling back to the
     copy cached on the last visit, so a rebuild reaches phones as soon as they
     next open it with signal.
   - Leaflet from cdnjs is cache-first (pinned version, never changes).
   - Map tiles and Commons photos are cache-first, capped; oldest dropped first.
     They're fetched with CORS (the layers set crossOrigin) so the cache holds
     real responses, not opaque ones that browsers pad to megabytes each.
   - Nothing is pre-cached speculatively: tile corridors for a 1,700 km loop are
     far too big. Look at the day's map with signal and it's yours offline.

   VERSION is stamped by scripts/build.py from a hash of the built page, so each
   deploy replaces the page cache. The tile cache survives deploys. */
'use strict';

const VERSION = '__BUILD__';
const APP = 'aotearoa-app-' + VERSION;
const TILES = 'aotearoa-tiles-v1';
const TILE_CAP = 2500;                   // roughly 40 MB of satellite tiles
const PAGE_TIMEOUT = 4000;               // ms to wait for the network before using the cached page
const SHELL = [
  './',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js',
];
const TILE_HOSTS = /(arcgisonline\.com|cartocdn\.com|opentopomap\.org|wikimedia\.org|wikipedia\.org)$/;

self.addEventListener('install', e => {
  e.waitUntil(caches.open(APP).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k.startsWith('aotearoa-app-') && k !== APP).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (req.mode === 'navigate') { e.respondWith(pageFirst(req)); return; }
  if (url.origin === location.origin || SHELL.includes(req.url)) { e.respondWith(cacheFirst(req, APP)); return; }
  if (TILE_HOSTS.test(url.hostname)) { e.respondWith(tileFirst(req)); }
  // anything else (Open-Meteo, NIWA, Google) goes straight to the network
});

const withTimeout = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms))]);

async function pageFirst(req) {
  const cache = await caches.open(APP);
  try {
    const res = await withTimeout(fetch(req), PAGE_TIMEOUT);
    if (res.ok) cache.put('./', res.clone());
    return res;
  } catch (err) {
    return (await cache.match(req, { ignoreSearch: true })) || (await cache.match('./')) || Response.error();
  }
}

async function cacheFirst(req, name) {
  const cache = await caches.open(name);
  const hit = await cache.match(req, { ignoreSearch: true });
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

let puts = 0;
async function tileFirst(req) {
  const cache = await caches.open(TILES);
  const hit = await cache.match(req.url);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok && res.type !== 'opaque') {
    await cache.put(req.url, res.clone());
    if (++puts % 25 === 0) trim(cache);
  }
  return res;
}

async function trim(cache) {
  const keys = await cache.keys();           // insertion order in practice, so the oldest come first
  const extra = keys.length - TILE_CAP;
  for (let i = 0; i < extra; i++) await cache.delete(keys[i]);
}
