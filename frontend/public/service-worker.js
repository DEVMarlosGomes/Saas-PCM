/**
 * AURIX Service Worker — Fase 6 PWA
 *
 * Estratégia de cache:
 * - Shell (HTML/JS/CSS): Cache-First → serve offline, revalida em background
 * - API /ordens-servico GET: Network-First com fallback para cache de 24h
 * - API /equipamentos GET: Cache-First (dados mudam pouco)
 * - API mutations (POST/PATCH/DELETE): Network-Only — nunca cacheamos writes
 *
 * Segurança:
 * - Tokens JWT NÃO são cacheados aqui (ficam em memória no contexto React)
 * - Cache de API não armazena Authorization header
 * - Cache expira em 24h para dados de OS
 */

const CACHE_VERSION = "aurix-v1";
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const API_CACHE = `${CACHE_VERSION}-api`;

// Assets do app shell para pré-cache no install
const SHELL_URLS = [
  "/",
  "/static/js/main.chunk.js",
  "/static/js/bundle.js",
  "/static/css/main.chunk.css",
  "/manifest.json",
];

const API_CACHE_PATHS = [
  "/api/ordens-servico",
  "/api/equipamentos",
  "/api/setores",
  "/api/colaboradores",
];

const API_CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 horas

// ── Install ──────────────────────────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => {
      return Promise.allSettled(SHELL_URLS.map((url) => cache.add(url)));
    })
  );
  self.skipWaiting();
});

// ── Activate — limpar caches antigos ─────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("aurix-") && k !== SHELL_CACHE && k !== API_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Não interceptar requests de outros origins
  if (url.origin !== self.location.origin) return;

  // Mutations nunca são cacheadas
  if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) return;

  // API endpoints com cache
  const isApiCacheable = API_CACHE_PATHS.some((p) => url.pathname.startsWith(p));
  if (url.pathname.startsWith("/api/")) {
    if (isApiCacheable) {
      event.respondWith(networkFirstWithCache(request));
    }
    return;
  }

  // App shell: cache-first
  event.respondWith(cacheFirstWithNetwork(request));
});

/**
 * Network-First: tenta rede; se falhar, serve cache.
 * Salva resposta de sucesso no cache com timestamp.
 */
async function networkFirstWithCache(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const networkResponse = await fetch(request.clone());
    if (networkResponse.ok) {
      // Clona e injeta timestamp antes de guardar
      const body = await networkResponse.clone().text();
      const headers = new Headers(networkResponse.headers);
      headers.set("X-Cache-Timestamp", Date.now().toString());
      const augmented = new Response(body, {
        status: networkResponse.status,
        statusText: networkResponse.statusText,
        headers,
      });
      await cache.put(request, augmented);
    }
    return networkResponse;
  } catch {
    const cached = await cache.match(request);
    if (cached) {
      const ts = cached.headers.get("X-Cache-Timestamp");
      if (ts && Date.now() - parseInt(ts, 10) < API_CACHE_MAX_AGE_MS) {
        return cached;
      }
    }
    return new Response(JSON.stringify({ offline: true, detail: "Sem conexão" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

/**
 * Cache-First: serve do cache se disponível; atualiza em background.
 */
async function cacheFirstWithNetwork(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  if (cached) {
    // Revalida em background (stale-while-revalidate)
    fetch(request).then((res) => { if (res.ok) cache.put(request, res); }).catch(() => {});
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch {
    // Fallback para index.html (SPA navegação offline)
    const fallback = await cache.match("/");
    return fallback || new Response("Offline", { status: 503 });
  }
}

// ── Sync background (experimental) ───────────────────────────────────────────
self.addEventListener("sync", (event) => {
  if (event.tag === "aurix-sync-queue") {
    // A fila real é processada pelo offlineQueue.js no main thread
    // Este evento apenas notifica os clients para triggar o flush
    event.waitUntil(
      self.clients.matchAll().then((clients) => {
        clients.forEach((c) => c.postMessage({ type: "SYNC_NOW" }));
      })
    );
  }
});
