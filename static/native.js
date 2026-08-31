/**
 * Hermes WebUI — native platform integrations.
 *
 * Five capabilities that make an installed PWA behave like an app rather than a
 * bookmark. Each one is a progressive enhancement: unsupported means no-op, not
 * broken, because the support matrix here is genuinely split (Badging is
 * Chromium + installed-only, Vibration is Android-only, View Transitions
 * shipped in Safari 18, Web Share is everywhere but `files` is not).
 *
 * WHY ONE MODULE
 *   All five are "ask the platform for something and cope when it says no", and
 *   all five are called from several places. Inlining `try{ navigator.x() }catch{}`
 *   at each call site is how you end up with five slightly different fallbacks
 *   and one of them throwing on iOS. The capability checks live here once.
 *
 * WHAT IS DELIBERATELY NOT HERE
 *   Optimistic UI, the session-list skeleton, and hands-free voice already exist
 *   in this codebase (messages.js, sessions.js, boot.js respectively) — the
 *   roadmap's claim that "zero of nine" native-feel items were present was only
 *   grep-verified for five API names. Nothing is reimplemented here.
 */

(function () {
  'use strict';

  // ── Haptics ────────────────────────────────────────────────────────────────
  //
  // Android only. iOS Safari does not implement Vibration and ignores it
  // silently, which is the correct failure mode — a phone that does not buzz is
  // not a broken phone.
  //
  // Gated on a preference AND on prior user activation. The activation check is
  // not defensive coding: Chromium logs "Blocked call to navigator.vibrate
  // because user hasn't tapped on the frame or any embedded frame yet" to the
  // console, and this repo has a smoke test that asserts zero console output.
  var HAPTIC_PREF_KEY = 'hermes-haptics';

  function hapticsSupported() {
    try {
      return typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function';
    } catch (_e) {
      return false;
    }
  }

  function hapticsEnabled() {
    try {
      // Default ON: a confirmation buzz on send is the sort of thing people
      // notice only by its absence. Explicit 'false' turns it off.
      return localStorage.getItem(HAPTIC_PREF_KEY) !== 'false';
    } catch (_e) {
      return true;
    }
  }

  function _hasUserActivation() {
    try {
      if (navigator.userActivation && typeof navigator.userActivation.hasBeenActive === 'boolean') {
        return navigator.userActivation.hasBeenActive;
      }
    } catch (_e) { /* fall through */ }
    return true;  // can't tell — let the browser decide
  }

  /**
   * A short confirmation buzz.
   *
   * @param {'tap'|'confirm'|'warn'} [kind] intensity, not a literal duration
   * @returns {boolean} whether the platform accepted it
   */
  function haptic(kind) {
    if (!hapticsSupported() || !hapticsEnabled() || !_hasUserActivation()) return false;
    // Kept short on purpose. Anything longer than ~30 ms reads as an error
    // buzz rather than an acknowledgement, and a pattern reads as an alarm.
    var ms = kind === 'warn' ? [12, 40, 12] : (kind === 'confirm' ? 18 : 10);
    try {
      return navigator.vibrate(ms) === true;
    } catch (_e) {
      return false;
    }
  }

  // ── App badge ──────────────────────────────────────────────────────────────
  //
  // The count of things blocking the agent — pending approvals — on the
  // home-screen icon. The natural pair for the push notifications from P0.2: a
  // push tells you once, a badge keeps telling you.
  //
  // Chromium-only and installed-only. Calling it in a plain tab rejects, which
  // is why every call is caught rather than checked: `'setAppBadge' in navigator`
  // is true in a tab where it will still fail.
  var _lastBadge = null;

  function badgeSupported() {
    try {
      return typeof navigator !== 'undefined' && typeof navigator.setAppBadge === 'function';
    } catch (_e) {
      return false;
    }
  }

  /**
   * @param {number} count 0 clears the badge
   * @returns {Promise<boolean>}
   */
  function setBadge(count) {
    var n = Math.max(0, Math.floor(Number(count) || 0));
    // Skipped when unchanged: this is called from approval polling, which fires
    // every couple of seconds, and each call is an IPC hop to the OS shell.
    if (n === _lastBadge) return Promise.resolve(true);
    if (!badgeSupported()) { _lastBadge = n; return Promise.resolve(false); }
    _lastBadge = n;
    try {
      var p = n > 0 ? navigator.setAppBadge(n) : navigator.clearAppBadge();
      return Promise.resolve(p).then(function () { return true; }, function () { return false; });
    } catch (_e) {
      return Promise.resolve(false);
    }
  }

  function clearBadge() {
    return setBadge(0);
  }

  // ── Web Share ──────────────────────────────────────────────────────────────
  //
  // The outbound half of Share Target: hand a session to another app instead of
  // routing everything through a clipboard copy.
  //
  // `navigator.canShare({files})` is a separate question from
  // `navigator.share` existing — Android supports files, several desktop
  // browsers support only text/url — so callers ask before building a File.
  function shareSupported() {
    try {
      return typeof navigator !== 'undefined' && typeof navigator.share === 'function';
    } catch (_e) {
      return false;
    }
  }

  function canShareFiles(files) {
    try {
      if (!shareSupported() || typeof navigator.canShare !== 'function') return false;
      return navigator.canShare({ files: files });
    } catch (_e) {
      return false;
    }
  }

  /**
   * @param {{title?:string, text?:string, url?:string, files?:File[]}} data
   * @returns {Promise<'shared'|'cancelled'|'unsupported'|'failed'>}
   *
   * `cancelled` is reported distinctly from `failed` because the caller must not
   * show an error toast when the user simply dismissed the OS sheet — the
   * commonest outcome of opening one.
   */
  function share(data) {
    if (!shareSupported()) return Promise.resolve('unsupported');
    var payload = {};
    if (data && data.title) payload.title = String(data.title);
    if (data && data.text) payload.text = String(data.text);
    if (data && data.url) payload.url = String(data.url);
    if (data && data.files && data.files.length && canShareFiles(data.files)) {
      payload.files = data.files;
    }
    if (!payload.title && !payload.text && !payload.url && !payload.files) {
      return Promise.resolve('unsupported');
    }
    try {
      return navigator.share(payload).then(function () {
        return 'shared';
      }, function (err) {
        var name = (err && err.name) || '';
        return (name === 'AbortError' || name === 'NotAllowedError') ? 'cancelled' : 'failed';
      });
    } catch (_e) {
      return Promise.resolve('failed');
    }
  }

  // ── View transitions ───────────────────────────────────────────────────────
  //
  // Pure progressive enhancement, and easy to get wrong in two ways:
  //
  //   1. The callback MUST still run when the API is missing, is disabled by
  //      prefers-reduced-motion, or when a transition is already in flight.
  //      Otherwise the DOM update is skipped entirely and the UI silently stops
  //      responding to navigation — a spectacular failure for a cosmetic feature.
  //   2. The returned promises REJECT when a transition is skipped (a second
  //      call, a hidden document). Unhandled, that is a console error on an
  //      ordinary double-tap.
  var _transitionActive = false;

  function viewTransitionsSupported() {
    try {
      return typeof document !== 'undefined' && typeof document.startViewTransition === 'function';
    } catch (_e) {
      return false;
    }
  }

  function _prefersReducedMotion() {
    try {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (_e) {
      return false;
    }
  }

  /**
   * Run `update` inside a view transition when the platform allows one.
   *
   * @param {Function} update the DOM mutation; always runs exactly once
   * @param {{name?:string}} [opts] sets `data-vt` on <html> so CSS can vary the
   *   animation per navigation kind
   * @returns {boolean} whether a transition was actually started
   */
  function viewTransition(update, opts) {
    if (typeof update !== 'function') return false;
    if (
      !viewTransitionsSupported()
      || _prefersReducedMotion()
      || _transitionActive
      || (typeof document !== 'undefined' && document.visibilityState === 'hidden')
    ) {
      update();
      return false;
    }
    var name = (opts && opts.name) || '';
    var root = document.documentElement;
    _transitionActive = true;
    if (name) root.setAttribute('data-vt', name);
    var done = function () {
      _transitionActive = false;
      if (name) root.removeAttribute('data-vt');
    };
    try {
      var tr = document.startViewTransition(function () { update(); });
      // .finished rejects on a skipped transition; both handlers clean up.
      Promise.resolve(tr.finished).then(done, done);
      return true;
    } catch (_e) {
      done();
      update();
      return false;
    }
  }

  // ── Share Target inbox ─────────────────────────────────────────────────────
  //
  // The receiving end of the manifest's share_target. Two producers write here,
  // and this is the single consumer:
  //
  //   sw.js          intercepts the POST, stashes text AND files in the
  //                  `hermes-share-inbox` cache, redirects to ./?shared=1
  //   api/routes.py  fallback for when no service worker is controlling —
  //                  redirects with the text on the query string (no files)
  //
  // Read unconditionally at boot rather than only when ?shared=1 is present: if
  // the redirect's query string is lost (a bookmark, a restored tab, an
  // intermediate redirect) the shared content would otherwise sit in the cache
  // forever with no way out. The freshness window is what makes that safe.
  var SHARE_CACHE = 'hermes-share-inbox';
  var SHARE_META_URL = 'share-inbox/meta';
  var SHARE_MAX_AGE_MS = 5 * 60 * 1000;

  function _readShareCache() {
    if (!('caches' in window)) return Promise.resolve(null);
    return caches.open(SHARE_CACHE).then(function (cache) {
      return cache.match(SHARE_META_URL).then(function (res) {
        if (!res) return null;
        return res.json().then(function (meta) {
          if (!meta || typeof meta !== 'object') return null;
          // Stale entries are dropped rather than applied. Pasting text someone
          // shared last week into the composer is worse than losing it.
          if (!meta.ts || (Date.now() - Number(meta.ts)) > SHARE_MAX_AGE_MS) {
            return cache.delete(SHARE_META_URL).then(function () { return null; });
          }
          var fileKeys = Array.isArray(meta.files) ? meta.files : [];
          return Promise.all(fileKeys.map(function (f) {
            return cache.match(f.key).then(function (r) {
              if (!r) return null;
              return r.blob().then(function (blob) {
                try {
                  return new File([blob], f.name || 'shared', { type: f.type || blob.type || '' });
                } catch (_e) {
                  return null;
                }
              });
            }).catch(function () { return null; });
          })).then(function (files) {
            meta.fileObjects = files.filter(Boolean);
            return meta;
          });
        }).catch(function () { return null; });
      });
    }).catch(function () { return null; });
  }

  function _clearShareCache() {
    if (!('caches' in window)) return Promise.resolve();
    return caches.delete(SHARE_CACHE).catch(function () { });
  }

  function _readShareQuery() {
    try {
      var q = new URLSearchParams(location.search);
      var text = q.get('share_text') || '';
      var title = q.get('share_title') || '';
      var url = q.get('share_url') || '';
      if (!text && !title && !url) return null;
      return { text: text, title: title, url: url, ts: Date.now(), fileObjects: [] };
    } catch (_e) {
      return null;
    }
  }

  function _stripShareQuery() {
    try {
      var u = new URL(location.href);
      var touched = false;
      // Every parameter the two share paths can add, including the
      // files-dropped flag the server fallback sets — leaving that one behind
      // means a reload re-shows the "files need the app open" note forever.
      ['share_text', 'share_title', 'share_url', 'share_files_dropped', 'shared'].forEach(function (k) {
        if (u.searchParams.has(k)) { u.searchParams.delete(k); touched = true; }
      });
      if (touched) history.replaceState(null, '', u.pathname + (u.search || '') + (u.hash || ''));
    } catch (_e) { /* URL hygiene only */ }
  }

  // Flatten what another app sent into the one string a composer can hold.
  // Order matters: the text is what the user selected, the URL is where it came
  // from, and a title without either is all we have.
  function shareTextFor(meta) {
    if (!meta) return '';
    var parts = [];
    if (meta.text) parts.push(String(meta.text).trim());
    var url = meta.url ? String(meta.url).trim() : '';
    // Android frequently puts the URL inside `text` as well; appending it again
    // gives the agent the same link twice.
    if (url && parts.indexOf(url) === -1 && (!parts[0] || parts[0].indexOf(url) === -1)) {
      parts.push(url);
    }
    if (!parts.length && meta.title) parts.push(String(meta.title).trim());
    return parts.join('\n\n').trim();
  }

  /**
   * Consume anything shared into the app and hand it to `apply`.
   *
   * @param {(payload:{text:string, files:File[]}) => void} apply
   * @returns {Promise<boolean>} whether anything was delivered
   */
  function consumePendingShare(apply) {
    if (typeof apply !== 'function') return Promise.resolve(false);
    var fromQuery = _readShareQuery();
    return _readShareCache().then(function (fromCache) {
      var meta = fromCache || fromQuery;
      if (!meta) return false;
      var text = shareTextFor(meta);
      var files = meta.fileObjects || [];
      if (!text && !files.length) return _clearShareCache().then(function () { return false; });
      try {
        apply({ text: text, files: files });
      } finally {
        _stripShareQuery();
        void _clearShareCache();
      }
      return true;
    }).catch(function () { return false; });
  }

  window.HermesNative = {
    haptic: haptic,
    hapticsSupported: hapticsSupported,
    hapticsEnabled: hapticsEnabled,
    HAPTIC_PREF_KEY: HAPTIC_PREF_KEY,

    setBadge: setBadge,
    clearBadge: clearBadge,
    badgeSupported: badgeSupported,

    share: share,
    shareSupported: shareSupported,
    canShareFiles: canShareFiles,

    viewTransition: viewTransition,
    viewTransitionsSupported: viewTransitionsSupported,

    consumePendingShare: consumePendingShare,
    shareTextFor: shareTextFor,
    SHARE_CACHE: SHARE_CACHE,
    SHARE_META_URL: SHARE_META_URL,
  };
})();
