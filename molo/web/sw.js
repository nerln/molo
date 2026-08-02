/* Service worker minimo: mette in cache solo il guscio dell'interfaccia.
   Serve a due cose: rendere Molo installabile sul telefono, e non lasciare una
   pagina bianca quando il computer che fa da server è spento.
   Le chiamate API non vengono mai messe in cache: mostrare una coda vecchia
   sarebbe peggio che mostrare un errore. */

const CACHE = "molo-shell-v2";
const SHELL = ["/", "/static/app.css", "/static/app.js", "/static/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.pathname.startsWith("/api") || url.pathname === "/ws") return;

  event.respondWith(
    fetch(event.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(event.request, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match("/")))
  );
});
