/**
 * Service Worker registration — Fase 6 PWA
 *
 * - Only registers in production or when REACT_APP_SW_DEV=true
 * - Listens for SYNC_NOW messages from the SW and triggers offlineQueue flush
 * - Exposes registerSyncTag() to request a background sync after a write
 */

let _swReg = null;
let _onSyncReady = null;

/**
 * Register the service worker. Call once at app startup.
 * @param {function} onSyncNow - called when SW says it's time to flush the queue
 */
export function register(onSyncNow) {
  if (!("serviceWorker" in navigator)) return;
  if (process.env.NODE_ENV !== "production" && !process.env.REACT_APP_SW_DEV) return;

  _onSyncReady = onSyncNow;

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js")
      .then((reg) => {
        _swReg = reg;
        console.log("[AURIX SW] registered, scope:", reg.scope);

        // Listen for SYNC_NOW messages from the service worker
        navigator.serviceWorker.addEventListener("message", (event) => {
          if (event.data?.type === "SYNC_NOW" && _onSyncReady) {
            _onSyncReady();
          }
        });

        // Also flush when coming back online
        window.addEventListener("online", () => {
          if (_onSyncReady) _onSyncReady();
        });
      })
      .catch((err) => console.warn("[AURIX SW] registration failed:", err));
  });
}

/**
 * Request a background sync tag (triggers SYNC_NOW when online).
 * Falls back to immediate call if Background Sync API is unavailable.
 * @param {function} fallback - called immediately if Background Sync unavailable
 */
export async function registerSyncTag(fallback) {
  if (_swReg && "sync" in _swReg) {
    try {
      await _swReg.sync.register("aurix-sync-queue");
      return;
    } catch (e) {
      console.warn("[AURIX SW] Background Sync not available:", e);
    }
  }
  if (navigator.onLine && fallback) fallback();
}

export function unregister() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.ready
    .then((reg) => reg.unregister())
    .catch(() => {});
}
