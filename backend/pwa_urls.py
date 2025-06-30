# backend/pwa_urls.py

from django.urls import path
from .views import pwa_views  # Changed from . import pwa_views to .views import pwa_views

urlpatterns = [
    path('manifest.json', pwa_views.ManifestView.as_view(), name='manifest'),
    path('sw.js', pwa_views.ServiceWorkerView.as_view(), name='service_worker'),
    path('offline/', pwa_views.OfflineView.as_view(), name='offline'),
]