/**
 * Offline Sync Queue — Fase 6 PWA
 *
 * Persists pending mutations to IndexedDB so they survive page refreshes.
 * When the network comes back, flushQueue() replays them in order.
 * Conflict resolution: server wins if version mismatch; client wins for
 * fields that changed after the last known sync_at timestamp.
 *
 * Security: tokens are NOT stored here — they come from the in-memory
 * auth context at flush time. IndexedDB is origin-scoped (not accessible
 * from other origins or service workers of other domains).
 */

const DB_NAME = "aurix_offline_queue";
const STORE_NAME = "pending_ops";
const DB_VERSION = 1;

let _db = null;

function openDB() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
        store.createIndex("created_at", "created_at", { unique: false });
      }
    };
    req.onsuccess = (e) => { _db = e.target.result; resolve(_db); };
    req.onerror = (e) => reject(e.target.error);
  });
}

/**
 * Enqueue a pending operation.
 * @param {object} op - { method, url, body, resource_type, resource_id, client_timestamp }
 */
export async function enqueue(op) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const req = store.add({
      ...op,
      created_at: Date.now(),
      attempts: 0,
    });
    req.onsuccess = () => resolve(req.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

/**
 * Get all pending operations in insertion order.
 */
export async function getQueue() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

/**
 * Remove a successfully synced operation by id.
 */
async function dequeue(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).delete(id);
    tx.oncomplete = resolve;
    tx.onerror = (e) => reject(e.target.error);
  });
}

/**
 * Increment the attempt counter for a failed op.
 */
async function incrementAttempt(op) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const req = store.put({ ...op, attempts: (op.attempts || 0) + 1 });
    req.onsuccess = resolve;
    req.onerror = (e) => reject(e.target.error);
  });
}

/**
 * Flush all queued operations.
 * @param {string} accessToken - current JWT from auth context (never from cache)
 * @returns {{ synced: number, failed: number, conflicts: Array }}
 */
export async function flushQueue(accessToken) {
  if (!navigator.onLine) return { synced: 0, failed: 0, conflicts: [] };

  const ops = await getQueue();
  if (ops.length === 0) return { synced: 0, failed: 0, conflicts: [] };

  let synced = 0;
  let failed = 0;
  const conflicts = [];

  for (const op of ops) {
    if (op.attempts >= 3) {
      // Give up after 3 attempts — leave in queue for manual resolution
      failed++;
      continue;
    }

    try {
      const res = await fetch(op.url, {
        method: op.method,
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${accessToken}`,
          "X-Offline-Sync": "true",
          "X-Client-Timestamp": String(op.client_timestamp || op.created_at),
        },
        body: op.body ? JSON.stringify(op.body) : undefined,
      });

      if (res.status === 409) {
        // Conflict — server has a newer version
        const data = await res.json().catch(() => ({}));
        conflicts.push({ op, server_version: data });
        await dequeue(op.id);
      } else if (res.ok) {
        await dequeue(op.id);
        synced++;
      } else if (res.status >= 400 && res.status < 500) {
        // Client error (e.g. 404 resource deleted) — discard
        await dequeue(op.id);
        failed++;
      } else {
        // Server error — retry later
        await incrementAttempt(op);
        failed++;
      }
    } catch {
      // Network error — retry later
      await incrementAttempt(op);
      failed++;
    }
  }

  return { synced, failed, conflicts };
}

/**
 * Clear the entire queue (e.g. on logout).
 */
export async function clearQueue() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).clear();
    tx.oncomplete = resolve;
    tx.onerror = (e) => reject(e.target.error);
  });
}

/**
 * Count pending ops (for badge/indicator).
 */
export async function getPendingCount() {
  const ops = await getQueue();
  return ops.length;
}
