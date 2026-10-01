// Service worker do PromoTrix (PWA): cache simples para abrir offline e as notificações de promoção.
// Nunca cacheia /api. Baseado no do Fintrix.
const VERSAO = "promotrix-v1";
const ESTATICOS = `${VERSAO}-estaticos`;
const PAGINAS = `${VERSAO}-paginas`;

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(ESTATICOS).then((c) => c.addAll(["/manifest.webmanifest"]).catch(() => {})));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((chaves) => Promise.all(chaves.filter((k) => !k.startsWith(VERSAO)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (url.pathname.startsWith("/_next/static") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.match(request).then(
        (guardado) =>
          guardado ||
          fetch(request).then((res) => {
            const copia = res.clone();
            caches.open(ESTATICOS).then((c) => c.put(request, copia));
            return res;
          }),
      ),
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copia = res.clone();
          caches.open(PAGINAS).then((c) => c.put(request, copia));
          return res;
        })
        .catch(() => caches.match(request).then((guardado) => guardado || caches.match("/"))),
    );
  }
});

// --- Notificação de promoção importante ---
self.addEventListener("push", (event) => {
  let dados = { title: "PromoTrix", body: "Promoção nova dentro do alvo.", url: "/", tag: "promotrix" };
  try {
    if (event.data) dados = { ...dados, ...event.data.json() };
  } catch {
    if (event.data) dados.body = event.data.text();
  }
  event.waitUntil(
    self.registration.showNotification(dados.title, {
      body: dados.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: dados.tag,
      data: { url: dados.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destino = (event.notification.data && event.notification.data.url) || "/";
  // Link do Pelando abre numa janela nova; link interno reaproveita a janela do app.
  if (!destino.startsWith("/")) {
    event.waitUntil(self.clients.openWindow(destino));
    return;
  }
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((janelas) => {
      for (const j of janelas) {
        if ("focus" in j) {
          j.navigate(destino);
          return j.focus();
        }
      }
      return self.clients.openWindow(destino);
    }),
  );
});
