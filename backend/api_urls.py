

# backend/api_urls.py

from django.urls import path, include
from .api import views as api_views

app_name = 'api'

urlpatterns = [
    # API Authentication
    path('auth/', include([
        path('login/', api_views.APILoginView.as_view(), name='api_login'),
        path('logout/', api_views.APILogoutView.as_view(), name='api_logout'),
        path('user/', api_views.APIUserView.as_view(), name='api_user'),
    ])),
    
    # API Contact endpoints
    path('contacts/', include([
        path('', api_views.ContactListAPIView.as_view(), name='api_contact_list'),
        path('<uuid:pk>/', api_views.ContactDetailAPIView.as_view(), name='api_contact_detail'),
        path('bulk-import/', api_views.ContactBulkImportAPIView.as_view(), name='api_contact_bulk_import'),
    ])),
    
    # API Campaign endpoints
    path('campaigns/', include([
        path('', api_views.CampaignListAPIView.as_view(), name='api_campaign_list'),
        path('<uuid:pk>/', api_views.CampaignDetailAPIView.as_view(), name='api_campaign_detail'),
        path('<uuid:pk>/send/', api_views.CampaignSendAPIView.as_view(), name='api_campaign_send'),
        path('<uuid:pk>/analytics/', api_views.CampaignAnalyticsAPIView.as_view(), name='api_campaign_analytics'),
    ])),
    
    # API Analytics endpoints
    path('analytics/', include([
        path('overview/', api_views.AnalyticsOverviewAPIView.as_view(), name='api_analytics_overview'),
        path('campaigns/', api_views.CampaignAnalyticsAPIView.as_view(), name='api_campaign_analytics'),
    ])),
]
