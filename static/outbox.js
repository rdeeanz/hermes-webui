/**
 * Hermes WebUI — offline send queue (outbox).
 *
 * WHY INDEXEDDB AND NOT BACKGROUND SYNC
 *   The obvious way to write this is `registration.sync.register('outbox')` and
 *   let the browser flush the queue when connectivity returns. Safari does not
 *   implement Background Sync, and iOS Safari is the single most likely place
 *   for a Hermes tab to be offline — a phone in a lift, a train, a basement.
 *   A queue that only flushes on Chrome is a queue that fails exactly where it
 *   was needed. So the durable store is IndexedDB (available everywhere,
 *   survives a tab crash and a browser restart, unlike an in-memory array) and
 *   the flush is driven by the page: on `online`, on load, on visibility, and
 *   on demand.
 *
 * WHY NOT localStorage
 *   The existing per-session queue (`hermes-queue-<sid>` in ui.js) uses it, and
 *   for a handful of short strings that is fine. This queue holds whole
 *   messages, is written from a failure path where the user has no other copy
 *   of what they typed, and localStorage is synchronous, ~5 MB, and the first
 *   thing an over-eager "clear site data" removes. IndexedDB is the right store
 *   for the only copy of someone's unsent work.
 *
 * WHAT IT DOES NOT DO
 *   It does not retry forever and it does not reorder. Entries flush oldest
 *   first, one at a time; a server rejection (4xx that is not 408/429) drops the
 *   entry and records the reason, because replaying a message the server has
 *   already refused just fails again on every future flush. A network failure
 *   stops the flush and leaves everything queued.
 */

(function () {
  'use strict';

  var DB_NAME = 'hermes-outbox';
  var DB_VERSION = 1;
  var STORE = 'sends';

  // A send that has failed this many times with a *server* error is dropped
  // rather than replayed forever. Network failures do not count towards it —
  // being offline for a week is not the message's fault.
  var MAX_ATTEMPTS = 5;

  var _dbPromise = null;
  var _flushing = null;
  var _listeners = [];

  function _supported() {
    try {
      return typeof indexedDB !== 'undefined' && indexedDB !== null;
    } catch (_e) {
      return false;
    }
  }

  function _openDb() {
    if (!_supported()) return Promise.reject(new Error('IndexedDB unavailable'));
    if (_dbPromise) return _dbPromise;
    _dbPromise = new Promise(function (resolve, reject) {
      var req;
      try {
        req = indexedDB.open(DB_NAME, DB_VERSION);
      } catch (e) {
        reject(e);
        return;
      }
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          var store = db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
          store.createIndex('queued_at', 'queued_at');
          store.createIndex('session_id', 'session_id');
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error || new Error('IndexedDB open failed')); };
      // Private browsing on some builds resolves neither handler.
      req.onblocked = function () { reject(new Error('IndexedDB blocked')); };
    });
    // A failed open must not be cached, or one transient failure disables the
    // outbox for the lifetime of the tab.
    _dbPromise.catch(function () { _dbPromise = null; });
    return _dbPromise;
  }

  function _tx(mode, fn) {
    return _openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, mode);
        var store = tx.objectStore(STORE);
        var out;
        try {
          out = fn(store);
        } catch (e) {
          reject(e);
          return;
        }
        tx.oncomplete = function () { resolve(out && out.result !== undefined ? out.result : out); };
        tx.onerror = function () { reject(tx.error || new Error('IndexedDB transaction failed')); };
        tx.onabort = function () { reject(tx.error || new Error('IndexedDB transaction aborted')); };
      });
    });
  }

  function _emit(detail) {
    var listeners = _listeners.slice();
    for (var i = 0; i < listeners.length; i++) {
      try { listeners[i](detail); } catch (_e) { }
    }
    try {
      window.dispatchEvent(new CustomEvent('hermes:outbox-change', { detail: detail }));
    } catch (_e) { }
  }

  /**
   * Queue one send.
   *
   * @param {{session_id:string, payload:object, display_text?:string}} entry
   * @returns {Promise<number|null>} the queued id, or null if it could not be stored
   */
  function enqueue(entry) {
    if (!entry || !entry.session_id || !entry.payload) {
      return Promise.resolve(null);
    }
    var record = {
      session_id: String(entry.session_id),
      payload: entry.payload,
      display_text: String(entry.display_text || ''),
      queued_at: Date.now(),
      attempts: 0,
      last_error: '',
    };
    return _tx('readwrite', function (store) { return store.add(record); })
      .then(function (id) {
        _emit({ reason: 'enqueued', session_id: record.session_id });
        return id;
      })
      .catch(function (e) {
        // Reported rather than swallowed: the caller decides whether to restore
        // the composer draft, and it can only decide that correctly if it knows
        // the queue did not take the message.
        try { console.warn('[outbox] enqueue failed', e); } catch (_e) { }
        return null;
      });
  }

  /** @returns {Promise<Array>} queued entries, oldest first. */
  function list() {
    return _tx('readonly', function (store) { return store.getAll(); })
      .then(function (rows) {
        var all = Array.isArray(rows) ? rows.slice() : [];
        all.sort(function (a, b) { return (a.queued_at || 0) - (b.queued_at || 0); });
        return all;
      })
      .catch(function () { return []; });
  }

  /** @returns {Promise<number>} */
  function count() {
    return _tx('readonly', function (store) { return store.count(); })
      .then(function (n) { return Number(n) || 0; })
      .catch(function () { return 0; });
  }

  function remove(id) {
    return _tx('readwrite', function (store) { return store.delete(id); })
      .then(function () { return true; })
      .catch(function () { return false; });
  }

  function _update(record) {
    return _tx('readwrite', function (store) { return store.put(record); })
      .catch(function () { return null; });
  }

  function clear() {
    return _tx('readwrite', function (store) { return store.clear(); })
      .then(function () { _emit({ reason: 'cleared' }); return true; })
      .catch(function () { return false; });
  }

  function _startUrl() {
    var base = (typeof document !== 'undefined' && document.baseURI) || location.href;
    return new URL('api/chat/start', base).href;
  }

  // A 4xx that is not a timeout or a rate limit will fail identically on every
  // future attempt: the session is gone, the model is invalid, the payload is
  // rejected. Replaying it forever is worse than dropping it with a reason.
  function _isPermanentRejection(status) {
    return status >= 400 && status < 500 && status !== 408 && status !== 429;
  }

  function _sendOne(record) {
    return fetch(_startUrl(), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(record.payload),
    }).then(function (res) {
      if (res.ok) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          return { outcome: 'sent', data: data };
        });
      }
      if (res.status === 401 || res.status === 403) {
        // Not the message's fault and not retryable from here — stop the whole
        // flush so the queue survives until the user logs back in.
        return { outcome: 'unauthorized', status: res.status };
      }
      return res.text().catch(function () { return ''; }).then(function (text) {
        var message = text;
        try {
          var parsed = JSON.parse(text);
          message = parsed.error || parsed.message || text;
        } catch (_e) { }
        return {
          outcome: _isPermanentRejection(res.status) ? 'rejected' : 'retry',
          status: res.status,
          error: String(message || ('HTTP ' + res.status)).slice(0, 500),
        };
      });
    }).catch(function (e) {
      // TypeError from fetch — still offline, or the connection dropped
      // mid-flush. Leave the entry alone.
      return { outcome: 'offline', error: String((e && e.message) || e) };
    });
  }

  /**
   * Send everything queued, oldest first.
   *
   * Serial on purpose: two sends racing into the same session hit the server's
   * "session already has an active stream" conflict, and the whole point of the
   * queue is that the user's messages arrive in the order they wrote them.
   *
   * @returns {Promise<{sent:number, dropped:number, remaining:number, stopped:string|null}>}
   */
  function flush() {
    if (_flushing) return _flushing;
    _flushing = (function () {
      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        return count().then(function (remaining) {
          return { sent: 0, dropped: 0, remaining: remaining, stopped: 'offline' };
        });
      }
      return list().then(function (entries) {
        var sent = 0;
        var dropped = 0;
        var stopped = null;

        function step(i) {
          if (i >= entries.length || stopped) return Promise.resolve();
          var record = entries[i];
          return _sendOne(record).then(function (result) {
            if (result.outcome === 'sent') {
              sent += 1;
              return remove(record.id).then(function () {
                _emit({
                  reason: 'sent',
                  session_id: record.session_id,
                  stream_id: (result.data && result.data.stream_id) || null,
                });
                return step(i + 1);
              });
            }
            if (result.outcome === 'offline') {
              stopped = 'offline';
              return undefined;
            }
            if (result.outcome === 'unauthorized') {
              stopped = 'unauthorized';
              return undefined;
            }
            if (result.outcome === 'rejected') {
              dropped += 1;
              return remove(record.id).then(function () {
                _emit({
                  reason: 'rejected',
                  session_id: record.session_id,
                  error: result.error || '',
                });
                return step(i + 1);
              });
            }
            // 5xx / 408 / 429 — worth another attempt later, but not forever.
            record.attempts = (Number(record.attempts) || 0) + 1;
            record.last_error = result.error || ('HTTP ' + result.status);
            if (record.attempts >= MAX_ATTEMPTS) {
              dropped += 1;
              return remove(record.id).then(function () {
                _emit({
                  reason: 'rejected',
                  session_id: record.session_id,
                  error: record.last_error,
                });
                return step(i + 1);
              });
            }
            return _update(record).then(function () {
              stopped = 'server-error';
            });
          });
        }

        return step(0).then(function () {
          return count().then(function (remaining) {
            if (sent || dropped) _emit({ reason: 'flushed', sent: sent, dropped: dropped });
            return { sent: sent, dropped: dropped, remaining: remaining, stopped: stopped };
          });
        });
      }).catch(function () {
        return { sent: 0, dropped: 0, remaining: 0, stopped: 'error' };
      });
    })();
    return _flushing.then(
      function (r) { _flushing = null; return r; },
      function (e) { _flushing = null; throw e; }
    );
  }

  function onChange(cb) {
    if (typeof cb !== 'function') return function () { };
    _listeners.push(cb);
    return function () {
      var i = _listeners.indexOf(cb);
      if (i >= 0) _listeners.splice(i, 1);
    };
  }

  // Flush triggers. `online` is the primary one; the others cover the cases it
  // misses — a browser that never fires it, a tab restored from bfcache, a PWA
  // resumed from the app switcher on iOS (where `online` is unreliable).
  function _maybeFlush() {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return;
    void flush();
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('online', _maybeFlush);
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') _maybeFlush();
    });
    // On load, drain anything left over from a previous session before the user
    // has a chance to wonder where their message went.
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', _maybeFlush, { once: true });
    } else {
      _maybeFlush();
    }
  }

  window.HermesOutbox = {
    supported: _supported,
    enqueue: enqueue,
    list: list,
    count: count,
    remove: remove,
    clear: clear,
    flush: flush,
    onChange: onChange,
    MAX_ATTEMPTS: MAX_ATTEMPTS,
    DB_NAME: DB_NAME,
    STORE_NAME: STORE,
  };
})();
