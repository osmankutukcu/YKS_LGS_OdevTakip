/** V10 opt-in desktop change-hint poll. No unsent homework is ever uploaded here.
 * It invokes the EXISTING guarded OfflineSync.downloadSnapshot() only after
 * a matching database id, a changed revision, and a clean local outbox.
 */
(function (window) {
  'use strict';
  const INTERVAL_MS = 20000;
  let last = null, running = false, stopped = false, failures = 0;
  let busy = false;
  function eligible() {
    const offline = window.OfflineSync;
    return !busy && !document.hidden &&
      !(document.activeElement && document.activeElement.matches('input,textarea,select,[contenteditable="true"]')) &&
      window.sessionStorage.getItem('yks_access') &&
      offline && offline.lastSnapshot && !offline.syncing && !offline.restoring &&
      !window.OfflineSecureStore?.busy && offline.pendingCount === 0 &&
      !offline.databaseMismatch && !offline.snapshotRefreshNeeded;
  }
  async function tick() {
    if (stopped || running || !eligible()) return;
    running = true;
    try {
      // originalApi handles the same X-Access-Key middleware as all existing sync APIs.
      if (typeof window._originalApi !== 'function') return;
      const hint = await window._originalApi('/api/sync/live10');
      if (hint.version !== 10 || hint.scope !== 'one_desktop_sqlite' ||
          hint.cloud_verified !== false || typeof hint.epoch !== 'string' ||
          !Number.isSafeInteger(hint.revision) || hint.revision < 0 ||
          typeof hint.database_id !== 'string') throw Error('Beklenmeyen değişiklik bildirimi');
      const sync = window.OfflineSync;
      if (!sync.lastSnapshot?.database_id || sync.lastSnapshot.database_id !== hint.database_id) {
        stopped = true;
        window.dispatchEvent(new CustomEvent('yks:live10-mismatch'));
        return; // Never mix databases or clear local user work.
      }
      failures = 0;
      if (last === null) { last = hint; return; }
      const changed = hint.epoch !== last.epoch || hint.revision !== last.revision;
      if (!changed) return;
      // A pending local edit or active form can become unsafe after await; recheck.
      if (!eligible()) return;
      busy = true;
      try {
        await sync.downloadSnapshot(); // V9 delta9 -> guarded V8/full fallback.
        last = hint; // Do not consume a change hint on a failed download.
        window.dispatchEvent(new CustomEvent('yks:live10-updated', {
          detail: { local: true, cloudVerified: false, at: new Date().toISOString() }
        }));
      } finally { busy = false; }
    } catch (err) {
      const code = Number(err?.httpStatus || 0);
      if (code === 401 || code === 403 || code === 404 || code === 503) stopped = true;
      failures++;
      if (failures === 1) console.info('[V10] Live hint paused:', err.message);
    } finally { running = false; }
  }
  function start() {
    if (window.__YKS_LIVE10_TIMER__) return;
    window.__YKS_LIVE10_TIMER__ = window.setInterval(tick, INTERVAL_MS);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
  window.OfflineLiveV10 = Object.freeze({checkNow: tick, isStopped:()=>stopped});
})(window);
