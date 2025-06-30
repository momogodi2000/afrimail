# afrimail/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('backend.urls')),
    path('api/', include('backend.api_urls')),
    
    # PWA related URLs
    path('manifest.json', include('backend.pwa_urls')),
    path('sw.js', include('backend.pwa_urls')),
    
    # Favicon redirect
    path('favicon.ico', RedirectView.as_view(url='/static/icons/favicon.ico', permanent=True)),
]

# Add hot reload URL for development
if settings.DEBUG:
    urlpatterns.append(path('__reload__/', include('django_browser_reload.urls')))

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom admin site configuration
admin.site.site_header = "AfriMail Pro Administration"
admin.site.site_title = "AfriMail Pro Admin"
admin.site.index_title = "Welcome to AfriMail Pro Administration"

