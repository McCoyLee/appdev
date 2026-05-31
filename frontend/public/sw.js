/* App For Oneself —— 极简 service worker（手写，无构建依赖）
 *
 * 目标：让应用「可安装」（PWA）+ 离线时还能打开外壳，而不是白屏。
 * 策略：
 *  - 导航请求（HTML）：network-first，断网回退到缓存的 index.html
 *  - 同源静态资源（JS/CSS/图标/字体）：stale-while-revalidate
 *  - /api 和 /healthz：永远直连网络，绝不缓存（数据真相在用户 GitHub）
 *
 * 注意：构建产物文件名带 hash，故不预缓存清单，全部运行时按需缓存。
 */

const CACHE = 'afo-shell-v1';
const SHELL = ['/', '/index.html', '/icon.svg', '/manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  // 跨域 或 后端接口：不插手
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/healthz')) return;

  // 导航：network-first，回退缓存外壳
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put('/index.html', copy));
          return resp;
        })
        .catch(() => caches.match('/index.html').then((r) => r || caches.match('/')))
    );
    return;
  }

  // 静态资源：stale-while-revalidate
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((resp) => {
          if (resp && resp.status === 200) {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
