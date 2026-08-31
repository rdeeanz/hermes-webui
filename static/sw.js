/**
 * Hermes WebUI Service Worker
 *
 * Two caches, with deliberately different lifetimes:
 *
 *   hermes-shell-<version>  static app shell (JS/CSS/vendor). Keyed by the build
 *                           version and wiped on every bump — code must never be
 *                           served stale.
 *   hermes-data-v1          a small amount of READ-ONLY API data (the session
 *                           list and session transcripts). Deliberately NOT
 *                           version-keyed: a deploy must not cost the user the
 *                           only copy of their sessions they can read on a
 *                           train. Wiped on logout and on an expired auth
 *                           session instead, which is the boundary that
 *                           actually matters.
 *
 * What the data cache is for: the offline shell used to be the literal string
 * "<h2>You are offline</h2>". The app now boots offline against cached data —
 * the session list renders, and the last transcript is readable — while sends
 * go to an IndexedDB outbox (static/outbox.js) instead of failing.
 *
 * What it is NOT for: anything that mutates. Only GET, only 200, only JSON, and
 * only the two read endpoints named below.
 */

// Cache version is injected by the server at request time (routes.py /sw.js handler).
// Bumps automatically whenever the git commit changes — no manual edits needed.
const CACHE_NAME = 'hermes-shell-__WEBUI_VERSION__';

// Survives version bumps on purpose — see the header comment. Bump the suffix
// only if the SHAPE of what is stored changes incompatibly.
const DATA_CACHE = 'hermes-data-v1';

// Static assets that form the app shell.
//
// Versioned assets (CSS + JS) include `?v=__WEBUI_VERSION__` to match the
// query string the page sends — see index.html. Without the version query
// here, every cache lookup against `?v=...` URLs would miss and fall through
// to network, defeating the pre-cache.
//
// Do not pre-cache './' or login assets here: under password auth they can be
// either the authenticated app shell or login code, and stale cached responses
// can make valid password submits fail until the user clears browser cache.
// Navigations populate './' only after a successful non-redirect network load.
const VQ = '?v=__WEBUI_VERSION__';
const SHELL_ASSETS = [
  './static/style.css' + VQ,
  './static/pwa-startup.js' + VQ,
  './static/boot.js' + VQ,
  './static/assistant_turn_anchors.js' + VQ,
  './static/ui.js' + VQ,
  './static/messages.js' + VQ,
  './static/sessions.js' + VQ,
  './static/panels.js' + VQ,
  './static/commands.js' + VQ,
  './static/icons.js' + VQ,
  // Both are <script defer> in index.html, so they were already on every cold
  // load — they were simply missing from this list, which meant an offline boot
  // came up without the outline pane or the extension settings surface.
  './static/outline.js' + VQ,
  './static/extension_settings.js' + VQ,
  // The send queue. It has to be present offline or there is nothing to queue
  // INTO when the user types on a train. Native integrations sit alongside it:
  // pre-cached because the Share Target inbox is read on boot, and a share can
  // be the very thing that opens the app offline.
  './static/outbox.js' + VQ,
  './static/native.js' + VQ,
  // Only the i18n core (runtime + English fallback + the language manifest).
  // The reader's own language bundle is deliberately NOT listed: which one it
  // is depends on localStorage, which a service worker cannot read. It gets
  // cached on first fetch by the shell rule below (network-first, cache
  // fallback), so the second visit is offline-capable in that language too.
  './static/i18n/core.js' + VQ,
  './static/workspace.js' + VQ,
  './static/terminal.js' + VQ,
  './static/onboarding.js' + VQ,
  './static/vendor/smd.min.js' + VQ,
  // Vendored Prism (previously CDN-hosted, so un-cacheable cross-origin).
  // Pre-caching it is what makes the offline shell genuinely self-contained.
  './static/vendor/prismjs/1.29.0/components/prism-core.min.js' + VQ,
  './static/vendor/prismjs/1.29.0/plugins/autoloader/prism-autoloader.min.js' + VQ,
  './static/vendor/prismjs/1.29.0/themes/prism-tomorrow.min.css' + VQ,
  './static/vendor/prismjs/1.29.0/themes/prism.min.css' + VQ,
  // The dividing line for lazily-loaded vendor code is whether it makes ALREADY
  // CACHED content readable, or whether it needs a live backend:
  //
  //   pre-cached    KaTeX, js-yaml — a cached transcript full of math or YAML
  //                 blocks renders completely without a server.
  //   not cached    xterm (~68 KiB) — a terminal is a live PTY; having the
  //                 library offline buys nothing. PDF.js (~1.7 MB) and Mermaid
  //                 (~3.3 MB) — too heavy to spend on every install for a
  //                 degraded-but-fine fallback (download link, code block).
  //
  // Prism's 150+ per-language grammar files are also absent: the autoloader
  // fetches one per language on demand, and pre-caching 1.3 MB to keep offline
  // syntax colours is not a trade worth making. Code blocks still render, just
  // unhighlighted.
  './static/vendor/katex/0.16.22/katex.min.css' + VQ,
  './static/vendor/katex/0.16.22/katex.min.js' + VQ,
  './static/vendor/js-yaml/4.1.0/js-yaml.min.js' + VQ,
  // The offline shell itself — see the navigation handler. Only reached on a
  // cold offline start, when even './' was never cached.
  './static/offline.html' + VQ,
  './static/favicon.svg',
  './static/favicon-32.png',
  './manifest.json',
];

function deleteOldShellCaches() {
  return caches.keys().then((keys) =>
    Promise.all(
      // DATA_CACHE is spared deliberately: it holds the user's readable-offline
      // sessions, and wiping it on every deploy would mean the offline shell is
      // empty exactly for the people who update most often.
      //
      // SHARE_CACHE is spared for a different reason: a Share Target POST can
      // land while an updated worker is installing, and this runs on install.
      // Wiping it there would swallow the thing the user just shared. It is
      // self-limiting anyway — the page consumes it on the next boot and drops
      // anything older than five minutes.
      keys
        .filter((k) => k !== CACHE_NAME && k !== DATA_CACHE && k !== SHARE_CACHE)
        .map((k) => caches.delete(k))
    )
  );
}

// Install: prune old shell caches first, then pre-cache the app shell. Doing
// this before caches.open(CACHE_NAME) avoids a temporary double-cache window on
// quota-sensitive browsers during frequent version bumps.
self.addEventListener('install', (event) => {
  event.waitUntil(
    deleteOldShellCaches().then(() =>
      caches.open(CACHE_NAME).then((cache) => {
        return cache.addAll(SHELL_ASSETS).catch((err) => {
          // Non-fatal: if any asset fails, still activate
          console.warn('[sw] Shell pre-cache partial failure:', err);
        });
      })
    )
  );
  self.skipWaiting();
});

// Activate: keep the old-cache cleanup as a safety net in case install was
// interrupted or an older worker was already waiting.
self.addEventListener('activate', (event) => {
  event.waitUntil(deleteOldShellCaches());
  self.clients.claim();
});

// ── Read-only API cache ──────────────────────────────────────────────────────
//
// Exactly two endpoints are cached, both pure reads:
//
//   GET …/api/sessions   the sidebar list
//   GET …/api/session    one session, including its transcript
//
// Anchored to the END of the path so the streaming siblings are never matched:
// /api/sessions/events and /api/sessions/gateway/stream are SSE, and handing a
// cached body to an EventSource would be an interesting way to break the app.
const API_SESSION_LIST_RE = /(?:^|\/)api\/sessions$/;
const API_SESSION_DETAIL_RE = /(?:^|\/)api\/session$/;

// Only ever store a response that is unambiguously the real thing. A 302 to
// /login arrives here as an opaque-ish redirected 200 HTML page; caching that
// as "your session list" would show a login form forever, offline.
function _isCacheableApiResponse(response) {
  return !!response
    && response.status === 200
    && !response.redirected
    && response.type !== 'opaqueredirect'
    && (response.headers.get('Content-Type') || '').includes('application/json');
}

// Stored normalized rather than as the raw fetch Response: the server sends
// Vary/Content-Encoding headers that make CacheStorage matching depend on
// request headers we do not control from here.
function _storableJson(body) {
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

function _matchDataCache(request) {
  return caches.match(request, { cacheName: DATA_CACHE, ignoreVary: true });
}

function _postToClients(message) {
  return self.clients
    .matchAll({ type: 'window', includeUncontrolled: true })
    .then((clients) => {
      clients.forEach((client) => {
        try { client.postMessage(message); } catch (_e) { }
      });
    })
    .catch(() => undefined);
}

// An expired auth session invalidates everything in the data cache at once:
// whoever logs in next must not inherit the previous reader's session list.
function _purgeDataCache() {
  return caches.delete(DATA_CACHE).catch(() => false);
}

// Fetch + store, resolving with { response, body }. `body` is null when the
// response was not storable, which is also what tells the callers not to
// compare or notify.
function _revalidateApi(request) {
  return fetch(new Request(request, { cache: 'no-store' })).then((response) => {
    if (response && (response.status === 401 || response.status === 403)) {
      return _purgeDataCache()
        .then(() => _postToClients({ type: 'hermes:offline-cache-invalidated' }))
        .then(() => ({ response, body: null }));
    }
    if (!_isCacheableApiResponse(response)) return { response, body: null };
    return response.clone().text().then((body) => {
      // Deliberately NOT awaited. A CacheStorage write hits disk, and the page
      // must not wait on it to receive data the network has already delivered.
      caches.open(DATA_CACHE)
        .then((cache) => cache.put(request, _storableJson(body)))
        .catch(() => undefined);
      return { response, body };
    });
  });
}

// Stale-while-revalidate, used ONLY when the page asks for it by sending
// `X-Hermes-Cache: swr`.
//
// Opting in per request rather than applying SWR to every /api/sessions call is
// the whole safety argument. The page sets the header on exactly one request:
// the cold-boot sidebar load, where the alternative is a skeleton. Every later
// poll — including the refetch right after a profile switch, which would
// otherwise flash the previous profile's sessions — stays network-first.
function _staleWhileRevalidate(event) {
  const request = event.request;
  return _matchDataCache(request).then((cached) => {
    if (!cached) {
      return _revalidateApi(request)
        .then((r) => r.response)
        .catch(() => _matchDataCache(request).then((c) => {
          if (c) return c;
          throw new Error('offline and nothing cached');
        }));
    }
    // Serve the cached list now; tell the page only if the network disagrees,
    // which is what stops this from looping: once the page refetches, the cache
    // matches the network and no further message is sent.
    event.waitUntil(
      cached.clone().text().then((oldBody) =>
        _revalidateApi(request).then(({ body }) => {
          if (body !== null && body !== oldBody) {
            return _postToClients({ type: 'hermes:sessions-updated' });
          }
          return undefined;
        })
      ).catch(() => undefined)
    );
    return cached;
  });
}

// Network-first with a cache fallback. The default for both endpoints: while
// there is a server, its answer is the only correct one. The cached copy exists
// for the case where there is no server to ask.
function _networkFirstApi(event) {
  const request = event.request;
  return _revalidateApi(request)
    .then((r) => r.response)
    .catch(() => _matchDataCache(request).then((cached) => {
      if (cached) return cached;
      // Nothing cached — fail exactly as a request without a service worker
      // would, so the page's own offline banner and retry logic still fire.
      throw new Error('offline and nothing cached');
    }));
}

// ── Share Target ─────────────────────────────────────────────────────────────
//
// The manifest declares `share_target` as a multipart POST to ./share-target.
// Handling it here rather than on the server is what makes FILES work: the
// service worker can read the FormData directly and stash the Blobs where the
// page can pick them up, with no upload round-trip and no server-side state.
//
// The response is a redirect, not content. A share target is a navigation, so
// whatever comes back becomes the page the user is looking at — it has to be
// the app.
const SHARE_TARGET_RE = /(?:^|\/)share-target\/?$/;
const SHARE_CACHE = 'hermes-share-inbox';
const SHARE_META_URL = 'share-inbox/meta';

// Bounds, because the sender is another application and this writes to disk.
const SHARE_MAX_FILES = 10;
const SHARE_MAX_FILE_BYTES = 25 * 1024 * 1024;
const SHARE_MAX_TEXT_CHARS = 100000;

function _shareRedirect() {
  const target = new URL('./?shared=1', self.registration.scope || './').href;
  // 303 specifically: it turns the POST into a GET on the redirect, which is
  // what makes the resulting history entry reloadable. A 302 would have the
  // browser re-POST on refresh and re-deliver the same share.
  return Response.redirect(target, 303);
}

function _handleShareTarget(event) {
  return event.request.formData().then((form) => {
    const text = (form.get('text') || '').toString().slice(0, SHARE_MAX_TEXT_CHARS);
    const title = (form.get('title') || '').toString().slice(0, 2000);
    const shared = (form.get('url') || '').toString().slice(0, 4000);

    const blobs = form.getAll('files')
      .filter((f) => f && typeof f === 'object' && typeof f.size === 'number')
      .filter((f) => f.size > 0 && f.size <= SHARE_MAX_FILE_BYTES)
      .slice(0, SHARE_MAX_FILES);

    return caches.open(SHARE_CACHE).then((cache) => {
      // Cleared first: an unconsumed share from a previous attempt must not be
      // merged into this one.
      return caches.delete(SHARE_CACHE)
        .then(() => caches.open(SHARE_CACHE))
        .then((fresh) => {
          const files = blobs.map((blob, i) => ({
            key: 'share-inbox/file/' + i,
            name: (blob.name || ('shared-' + i)).toString().slice(0, 255),
            type: blob.type || '',
            size: blob.size,
          }));
          const writes = blobs.map((blob, i) => fresh.put(
            files[i].key,
            new Response(blob, { headers: { 'Content-Type': files[i].type || 'application/octet-stream' } })
          ));
          writes.push(fresh.put(SHARE_META_URL, new Response(
            JSON.stringify({ text, title, url: shared, ts: Date.now(), files }),
            { headers: { 'Content-Type': 'application/json; charset=utf-8' } }
          )));
          return Promise.all(writes);
        })
        .then(() => _shareRedirect());
    });
  }).catch(() => {
    // Malformed form, quota exhausted, storage denied. Still land the user in
    // the app: a share that loses its payload is a disappointment, but a share
    // that shows a browser error page looks like the app is broken.
    return _shareRedirect();
  });
}

// Fetch strategy:
// - POST …/share-target → consumed here (Share Target API), never forwarded
// - GET /api/sessions and /api/session → cached (see above); everything else
//   under /api/*, plus /stream and /health → always network, never cached
// - Login assets → always network (never cache stale auth code)
// - Page navigations → network-first so auth redirects/cookies are honored
// - Shell assets → network-first with cache fallback
// - Everything else → network-only
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Never intercept cross-origin requests
  if (url.origin !== self.location.origin) return;

  // Never intercept the service worker script itself. Returning a cached sw.js
  // prevents the browser from seeing a new cache version after local patches.
  if (url.pathname.endsWith('/sw.js')) return;

  // Share Target. This MUST be tested before the navigation branch below: the
  // OS delivers a share as a POST whose `mode` is 'navigate', so the generic
  // navigation handler would forward it to the network and the user's shared
  // text would come back as whatever the server made of it.
  if (event.request.method === 'POST' && SHARE_TARGET_RE.test(url.pathname)) {
    event.respondWith(_handleShareTarget(event));
    return;
  }

  // Login assets must always hit the network. Older login.js builds have had
  // subpath-sensitive auth POST paths; if the service worker caches one, the
  // password can keep failing until the user manually clears browser cache.
  if (
    url.pathname.endsWith('/login') ||
    url.pathname.endsWith('/static/login.js')
  ) {
    return;
  }

  // The two read endpoints that back the offline shell. Checked BEFORE the
  // blanket /api/ bypass below, and narrowed hard: GET only, and the path must
  // END in the endpoint name so the SSE siblings fall through to the bypass.
  if (event.request.method === 'GET' && !url.pathname.includes('/stream')) {
    if (API_SESSION_LIST_RE.test(url.pathname)) {
      const wantsSwr = event.request.headers.get('X-Hermes-Cache') === 'swr';
      event.respondWith(
        wantsSwr ? _staleWhileRevalidate(event) : _networkFirstApi(event)
      );
      return;
    }
    if (API_SESSION_DETAIL_RE.test(url.pathname)) {
      event.respondWith(_networkFirstApi(event));
      return;
    }
  }

  // Every other API and streaming endpoint — always go to network.
  // The WebUI may be mounted under a subpath such as /hermes/, so API
  // requests can look like /hermes/api/sessions rather than /api/sessions.
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.includes('/api/') ||
    url.pathname.includes('/stream') ||
    url.pathname.startsWith('/health') ||
    url.pathname.includes('/health')
  ) {
    return; // let browser handle normally
  }

  // Page navigations must be network-first. A stale cached './' response can
  // otherwise hide the server's 302-to-login after auth expiry, or ignore a
  // freshly set login cookie until the user manually refreshes.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(new Request(event.request, { cache: 'no-store' })).then((response) => {
        if (
          event.request.method === 'GET' &&
          response.status === 200 &&
          !response.redirected
        ) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put('./', clone));
        }
        return response;
      }).catch(() => {
        // Offline. Preferred answer by a wide margin: the cached app shell.
        // It boots against the data cache above, so the sidebar fills in and
        // the last transcript is readable — a real offline app, not a notice.
        //
        // static/offline.html is the fallback for the one case the shell cannot
        // cover: a cold start where './' was never cached (installed from a
        // shortcut, first launch offline, storage evicted). It reads the same
        // data cache directly and renders the sessions read-only.
        return caches.match('./')
          .then((cached) => cached || caches.match('./static/offline.html' + VQ))
          .then((cached) => cached || caches.match('./static/offline.html'))
          .then((cached) => cached || new Response(
            // Last resort only: reached when even the pre-cache failed, so
            // there is nothing to render FROM. Kept deliberately dependency-free.
            '<html><body style="font-family:sans-serif;padding:2rem;background:#1a1a1a;color:#ccc">' +
            '<h2>You are offline</h2>' +
            '<p>Hermes requires a server connection. Please check your network and try again.</p>' +
            '</body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          ));
      })
    );
    return;
  }

  // Only explicit shell assets are cached. Everything else should hit the
  // network so stale one-off files (especially auth/login scripts) do not get
  // trapped in CacheStorage until a manual cache clear.
  const scopePath = new URL(self.registration.scope).pathname;
  const relPath = url.pathname.startsWith(scopePath)
    ? url.pathname.slice(scopePath.length)
    : url.pathname.replace(/^\/+/, '');
  const shellPath = './' + relPath.replace(/^\/+/, '') + url.search;
  if (!SHELL_ASSETS.includes(shellPath)) return;

  // Shell assets: network-first with cache fallback. This keeps offline support
  // but avoids executing stale JS/CSS after a local hotfix when WEBUI_VERSION
  // has not changed yet (e.g. before a guarded restart updates the ?v token).
  event.respondWith(
    fetch(new Request(event.request, { cache: 'no-store' })).then((response) => {
      if (
        event.request.method === 'GET' &&
        response.status === 200
      ) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
      }
      return response;
    }).catch(() => caches.match(event.request).then((cached) => cached || new Response('Offline', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    })))
  );
});


// ── Web Push ─────────────────────────────────────────────────────────────────
//
// The page already raises notifications itself when a stream finishes while the
// tab is backgrounded (messages.js). That path only works while a page is alive,
// which on a phone frequently means "not when it matters" — the browser is
// evicted while the screen is off, and a finished turn or a waiting approval
// goes unannounced. A push arrives regardless.
//
// The two paths overlap whenever a tab IS alive, so this suppresses the push if
// a visible window is already on the target page: the user is looking at it, and
// a system notification for something on screen is noise. A backgrounded or
// hidden window still gets the push, because there the page's own notification
// may never fire (throttled timers, suspended SSE).
self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_e) {
    // A push with a non-JSON body is not something this app sends, but a
    // malformed one must still produce *something* rather than being dropped —
    // silence is indistinguishable from a broken subscription.
    payload = { body: (event.data && event.data.text && event.data.text()) || '' };
  }

  const title = payload.title || 'Hermes';
  const url = payload.url || './';
  const targetPath = (() => {
    try { return new URL(url, self.registration.scope || './').pathname; } catch (_e) { return null; }
  })();

  const options = {
    body: payload.body || '',
    icon: 'static/favicon-192.png',
    badge: 'static/favicon-32.png',
    // Tagging by session collapses repeat notifications for the same
    // conversation instead of stacking one per turn.
    tag: payload.tag || 'hermes-webui',
    renotify: payload.renotify !== false,
    // Approvals block the agent until answered, and a crash or failed cron job
    // means work stopped and will not resume on its own — all three are worth
    // interrupting for. A completed turn is not: it can wait until you look.
    requireInteraction: (
      payload.kind === 'approval'
      || payload.kind === 'crash'
      || payload.kind === 'cron_failed'
    ),
    data: { url: url },
  };

  // App badge for a blocking approval, set from the worker so it appears even
  // when no page is alive to count anything. Deliberately the argument-less
  // form: the payload carries no count, and setAppBadge() with no argument is
  // the spec's "unspecified number" — a dot rather than a wrong number. The
  // page replaces it with the exact count via _syncApprovalAppBadge as soon as
  // it opens.
  if (payload.kind === 'approval') {
    event.waitUntil(
      Promise.resolve()
        .then(() => (self.navigator && self.navigator.setAppBadge)
          ? self.navigator.setAppBadge()
          : undefined)
        .catch(() => undefined)
    );
  }

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clients) => {
        const alreadyVisible = clients.some((client) => {
          if (client.visibilityState !== 'visible') return false;
          if (!targetPath) return false;
          try { return new URL(client.url).pathname === targetPath; } catch (_e) { return false; }
        });
        if (alreadyVisible) return undefined;
        return self.registration.showNotification(title, options);
      })
      .catch(() => self.registration.showNotification(title, options))
  );
});

// A push service can rotate a subscription without the user doing anything. The
// old endpoint stops working at that moment, so the page has to re-register —
// this tells any open client to do so, and the next page load re-subscribes
// anyway if none is listening.
// ── Messages from the page ───────────────────────────────────────────────────
//
// The only one that exists today is the logout purge. It matters: the data
// cache outlives version bumps by design, so without an explicit purge the next
// person to log in on a shared device would boot offline into the previous
// reader's session list. panels.js sends this before it navigates away, and the
// 401/403 path in _revalidateApi is the backstop for a session that simply
// expired rather than being logged out.
self.addEventListener('message', (event) => {
  const type = event && event.data && event.data.type;
  if (type !== 'hermes:purge-data-cache') return;
  const done = _purgeDataCache();
  if (event.waitUntil) event.waitUntil(done);
  // The caller awaits this so it can navigate only after the purge lands.
  if (event.ports && event.ports[0]) {
    done.then(() => {
      try { event.ports[0].postMessage({ ok: true }); } catch (_e) { }
    });
  }
});

self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      clients.forEach((client) => {
        try { client.postMessage({ type: 'hermes:push-resubscribe' }); } catch (_e) { }
      });
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const rawUrl = (event.notification.data && event.notification.data.url) || './';
  const targetUrl = new URL(rawUrl, self.registration.scope || './').href;
  const targetPath = new URL(targetUrl).pathname;
  const samePath = (clientUrl) => {
    try { return new URL(clientUrl).pathname === targetPath; } catch (_e) { return false; }
  };
  const sameOrigin = (clientUrl) => {
    try { return new URL(clientUrl).origin === self.location.origin; } catch (_e) { return false; }
  };
  event.waitUntil(
    self.clients.matchAll({type: 'window', includeUncontrolled: true}).then((clientList) => {
      // Match on pathname, not the full href: _sessionUrlForSid copies the
      // current page's query string + hash into the deep link, so an open tab
      // already on /session/<sid> would fail an exact-href match and spawn a
      // duplicate window.
      const targetClient = clientList.find((client) => samePath(client.url) && 'focus' in client);
      if (targetClient) return targetClient.focus();

      const openNotificationWindow = () => (
        self.clients.openWindow ? self.clients.openWindow(targetUrl) : undefined
      );
      const focusableClient = clientList.find((client) => sameOrigin(client.url) && 'focus' in client && 'navigate' in client);
      if (focusableClient && 'navigate' in focusableClient) {
        return focusableClient.navigate(targetUrl)
          .then((client) => (client && 'focus' in client ? client.focus() : focusableClient.focus()))
          .catch(() => focusableClient.focus());
      }
      return openNotificationWindow();
    })
  );
});
