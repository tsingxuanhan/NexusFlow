/**
 * Service Worker for Materials Research AI Workstation
 * 提供离线缓存支持
 */

const CACHE_NAME = 'ai-workstation-v1';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/models.html',
    '/monitor.html',
    '/commands.html',
    '/communication.html',
    '/knowledge.html',
    '/config.html',
    '/css/style.css',
    '/js/common.js',
    '/js/config.json',
    '/manifest.json'
];

// 安装事件 - 缓存静态资源
self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                // 立即激活
                return self.skipWaiting();
            })
    );
});

// 激活事件 - 清理旧缓存
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');
    
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME)
                        .map((name) => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                // 立即接管所有页面
                return self.clients.claim();
            })
    );
});

// 请求拦截 - 缓存优先策略
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // 跳过非GET请求
    if (request.method !== 'GET') {
        return;
    }
    
    // 跳过Chrome扩展等
    if (!url.protocol.startsWith('http')) {
        return;
    }
    
    // API请求 - 网络优先，降级到缓存
    if (url.port === '11434' || url.port === '9000' || url.port === '18789') {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    // 克隆响应并缓存
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME)
                        .then((cache) => {
                            cache.put(request, responseClone);
                        });
                    return response;
                })
                .catch(() => {
                    // 网络失败时返回缓存
                    return caches.match(request);
                })
        );
        return;
    }
    
    // 静态资源 - 缓存优先
    event.respondWith(
        caches.match(request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    // 返回缓存同时更新
                    fetch(request)
                        .then((response) => {
                            caches.open(CACHE_NAME)
                                .then((cache) => {
                                    cache.put(request, response);
                                });
                        })
                        .catch(() => {});
                    
                    return cachedResponse;
                }
                
                // 缓存未命中，网络获取
                return fetch(request)
                    .then((response) => {
                        // 缓存有效响应
                        if (response && response.status === 200) {
                            const responseClone = response.clone();
                            caches.open(CACHE_NAME)
                                .then((cache) => {
                                    cache.put(request, responseClone);
                                });
                        }
                        return response;
                    })
                    .catch(() => {
                        // 离线且无缓存时返回离线页面
                        if (request.destination === 'document') {
                            return caches.match('/index.html');
                        }
                    });
            })
    );
});

// 推送通知（预留）
self.addEventListener('push', (event) => {
    if (event.data) {
        const data = event.data.json();
        
        event.waitUntil(
            self.registration.showNotification(data.title || 'AI工作站', {
                body: data.body || '您有新的消息',
                icon: '/icon.png',
                badge: '/badge.png',
                tag: 'ai-workstation'
            })
        );
    }
});

// 点击通知
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    event.waitUntil(
        clients.matchAll({ type: 'window' })
            .then((clientList) => {
                // 如果已有窗口则聚焦
                for (const client of clientList) {
                    if (client.url.includes('/control-panel/') && 'focus' in client) {
                        return client.focus();
                    }
                }
                // 否则打开新窗口
                if (clients.openWindow) {
                    return clients.openWindow('/control-panel/');
                }
            })
    );
});
