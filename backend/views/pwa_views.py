# backend/views/pwa_views.py

from django.http import JsonResponse, HttpResponse
from django.views.generic import View, TemplateView
from django.conf import settings
from django.contrib.staticfiles import finders
import json
import os


class ManifestView(View):
    """PWA manifest.json view"""
    
    def get(self, request, *args, **kwargs):
        manifest = {
            "name": "AfriMail Pro",
            "short_name": "AfriMail",
            "description": "Professional Email Marketing Platform for Africa",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait-primary",
            "theme_color": "#1f2937",
            "background_color": "#ffffff",
            "categories": ["business", "productivity", "communication"],
            "lang": "en",
            "dir": "ltr",
            "icons": [
                {
                    "src": "/static/icons/icon-72x72.png",
                    "sizes": "72x72",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-96x96.png",
                    "sizes": "96x96",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-128x128.png",
                    "sizes": "128x128",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-144x144.png",
                    "sizes": "144x144",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-152x152.png",
                    "sizes": "152x152",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-192x192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-384x384.png",
                    "sizes": "384x384",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-512x512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable"
                }
            ],
            "screenshots": [
                {
                    "src": "/static/screenshots/desktop-1.png",
                    "sizes": "1280x720",
                    "type": "image/png",
                    "form_factor": "wide"
                },
                {
                    "src": "/static/screenshots/mobile-1.png",
                    "sizes": "320x568",
                    "type": "image/png",
                    "form_factor": "narrow"
                }
            ],
            "shortcuts": [
                {
                    "name": "Dashboard",
                    "short_name": "Dashboard",
                    "description": "View your email marketing dashboard",
                    "url": "/dashboard/",
                    "icons": [
                        {
                            "src": "/static/icons/shortcut-dashboard.png",
                            "sizes": "192x192"
                        }
                    ]
                },
                {
                    "name": "Contacts",
                    "short_name": "Contacts",
                    "description": "Manage your contact lists",
                    "url": "/contacts/",
                    "icons": [
                        {
                            "src": "/static/icons/shortcut-contacts.png",
                            "sizes": "192x192"
                        }
                    ]
                },
                {
                    "name": "Campaigns",
                    "short_name": "Campaigns",
                    "description": "Create and manage email campaigns",
                    "url": "/campaigns/",
                    "icons": [
                        {
                            "src": "/static/icons/shortcut-campaigns.png",
                            "sizes": "192x192"
                        }
                    ]
                }
            ],
            "related_applications": [],
            "prefer_related_applications": False
        }
        
        response = JsonResponse(manifest)
        response['Content-Type'] = 'application/manifest+json'
        return response


class ServiceWorkerView(View):
    """Service worker view"""
    
    def get(self, request, *args, **kwargs):
        service_worker_content = """
// AfriMail Pro Service Worker
const CACHE_NAME = 'afrimail-v1.0.0';
const STATIC_CACHE = 'afrimail-static-v1.0.0';
const DYNAMIC_CACHE = 'afrimail-dynamic-v1.0.0';

// Files to cache immediately
const STATIC_FILES = [
    '/',
    '/static/css/main.css',
    '/static/js/main.js',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    '/offline/',
];

// Install event
self.addEventListener('install', event => {
    console.log('Service Worker: Installing...');
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Service Worker: Caching static files');
                return cache.addAll(STATIC_FILES);
            })
            .catch(err => console.log('Service Worker: Cache failed', err))
    );
});

// Activate event
self.addEventListener('activate', event => {
    console.log('Service Worker: Activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== STATIC_CACHE && cache !== DYNAMIC_CACHE) {
                        console.log('Service Worker: Clearing old cache');
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
});

// Fetch event
self.addEventListener('fetch', event => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') return;
    
    // Skip Chrome extension requests
    if (event.request.url.includes('chrome-extension://')) return;
    
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Return cached version or fetch from network
                return response || fetch(event.request)
                    .then(fetchResponse => {
                        // Check if we received a valid response
                        if (!fetchResponse || fetchResponse.status !== 200 || fetchResponse.type !== 'basic') {
                            return fetchResponse;
                        }
                        
                        // Clone the response for caching
                        const responseToCache = fetchResponse.clone();
                        
                        // Cache dynamic content
                        caches.open(DYNAMIC_CACHE)
                            .then(cache => {
                                cache.put(event.request, responseToCache);
                            });
                        
                        return fetchResponse;
                    })
                    .catch(() => {
                        // Return offline page for navigation requests
                        if (event.request.mode === 'navigate') {
                            return caches.match('/offline/');
                        }
                        
                        // Return fallback for images
                        if (event.request.destination === 'image') {
                            return caches.match('/static/icons/icon-192x192.png');
                        }
                    });
            })
    );
});

// Background sync for offline actions
self.addEventListener('sync', event => {
    console.log('Service Worker: Background sync', event.tag);
    
    if (event.tag === 'background-sync') {
        event.waitUntil(doBackgroundSync());
    }
});

function doBackgroundSync() {
    // Handle offline actions when back online
    return fetch('/api/sync/')
        .then(response => response.json())
        .then(data => {
            console.log('Background sync completed', data);
        })
        .catch(err => {
            console.log('Background sync failed', err);
        });
}

// Push notifications
self.addEventListener('push', event => {
    console.log('Service Worker: Push received', event);
    
    const options = {
        body: event.data ? event.data.text() : 'New notification from AfriMail Pro',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/badge-72x72.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'explore',
                title: 'View',
                icon: '/static/icons/action-view.png'
            },
            {
                action: 'close',
                title: 'Close',
                icon: '/static/icons/action-close.png'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification('AfriMail Pro', options)
    );
});

// Notification click
self.addEventListener('notificationclick', event => {
    console.log('Service Worker: Notification clicked', event);
    event.notification.close();
    
    if (event.action === 'explore') {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

// Message from main thread
self.addEventListener('message', event => {
    console.log('Service Worker: Message received', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
"""
        
        response = HttpResponse(service_worker_content, content_type='application/javascript')
        response['Service-Worker-Allowed'] = '/'
        return response


class OfflineView(TemplateView):
    """Offline page view"""
    
    template_name = 'pwa/offline.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'You are offline',
            'message': 'Please check your internet connection and try again.',
        })
        return context
