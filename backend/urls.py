
# backend/urls.py

from django.urls import path, include
from . import views

app_name = 'backend'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Authentication URLs
    path('auth/', include([
        path('login/', views.LoginView.as_view(), name='login'),
        path('logout/', views.LogoutView.as_view(), name='logout'),
        path('register/', views.RegisterView.as_view(), name='register'),
        path('verify-email/<str:token>/', views.VerifyEmailView.as_view(), name='verify_email'),
        path('password-reset/', views.PasswordResetView.as_view(), name='password_reset'),
        path('password-reset-confirm/<str:token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
        path('profile/', views.ProfileView.as_view(), name='profile'),
        path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    ])),
    
    # Contact Management URLs
    path('contacts/', include([
        path('', views.ContactListView.as_view(), name='contact_list'),
        path('create/', views.ContactCreateView.as_view(), name='contact_create'),
        path('<uuid:pk>/', views.ContactDetailView.as_view(), name='contact_detail'),
        path('<uuid:pk>/edit/', views.ContactUpdateView.as_view(), name='contact_update'),
        path('<uuid:pk>/delete/', views.ContactDeleteView.as_view(), name='contact_delete'),
        path('import/', views.ContactImportView.as_view(), name='contact_import'),
        path('export/', views.ContactExportView.as_view(), name='contact_export'),
        path('bulk-actions/', views.ContactBulkActionsView.as_view(), name='contact_bulk_actions'),
    ])),
    
    # Contact Lists/Segments URLs
    path('lists/', include([
        path('', views.ContactListsView.as_view(), name='contact_lists'),
        path('create/', views.ContactListCreateView.as_view(), name='contact_list_create'),
        path('<uuid:pk>/', views.ContactListDetailView.as_view(), name='contact_list_detail'),
        path('<uuid:pk>/edit/', views.ContactListUpdateView.as_view(), name='contact_list_update'),
        path('<uuid:pk>/delete/', views.ContactListDeleteView.as_view(), name='contact_list_delete'),
    ])),
    
    # Email Campaign URLs
    path('campaigns/', include([
        path('', views.CampaignListView.as_view(), name='campaign_list'),
        path('create/', views.CampaignCreateView.as_view(), name='campaign_create'),
        path('<uuid:pk>/', views.CampaignDetailView.as_view(), name='campaign_detail'),
        path('<uuid:pk>/edit/', views.CampaignUpdateView.as_view(), name='campaign_update'),
        path('<uuid:pk>/delete/', views.CampaignDeleteView.as_view(), name='campaign_delete'),
        path('<uuid:pk>/send/', views.CampaignSendView.as_view(), name='campaign_send'),
        path('<uuid:pk>/preview/', views.CampaignPreviewView.as_view(), name='campaign_preview'),
        path('<uuid:pk>/duplicate/', views.CampaignDuplicateView.as_view(), name='campaign_duplicate'),
        path('<uuid:pk>/analytics/', views.CampaignAnalyticsView.as_view(), name='campaign_analytics'),
    ])),
    
    # Email Domain Configuration URLs
    path('email-config/', include([
        path('', views.EmailConfigListView.as_view(), name='email_config_list'),
        path('create/', views.EmailConfigCreateView.as_view(), name='email_config_create'),
        path('<uuid:pk>/', views.EmailConfigDetailView.as_view(), name='email_config_detail'),
        path('<uuid:pk>/edit/', views.EmailConfigUpdateView.as_view(), name='email_config_update'),
        path('<uuid:pk>/delete/', views.EmailConfigDeleteView.as_view(), name='email_config_delete'),
        path('<uuid:pk>/verify/', views.EmailConfigVerifyView.as_view(), name='email_config_verify'),
        path('<uuid:pk>/test/', views.EmailConfigTestView.as_view(), name='email_config_test'),
    ])),
    
    # Analytics & Reports URLs
    path('analytics/', include([
        path('', views.AnalyticsOverviewView.as_view(), name='analytics_overview'),
        path('campaigns/', views.CampaignAnalyticsListView.as_view(), name='campaign_analytics_list'),
        path('contacts/', views.ContactAnalyticsView.as_view(), name='contact_analytics'),
        path('reports/', views.ReportsView.as_view(), name='reports'),
        path('export-data/', views.ExportDataView.as_view(), name='export_data'),
    ])),
    
    # Admin URLs (Super Admin only)
    path('admin-panel/', include([
        path('', views.AdminDashboardView.as_view(), name='admin_dashboard'),
        path('users/', views.AdminUserListView.as_view(), name='admin_user_list'),
        path('users/<uuid:pk>/', views.AdminUserDetailView.as_view(), name='admin_user_detail'),
        path('users/<uuid:pk>/edit/', views.AdminUserUpdateView.as_view(), name='admin_user_update'),
        path('users/<uuid:pk>/delete/', views.AdminUserDeleteView.as_view(), name='admin_user_delete'),
        path('system-stats/', views.SystemStatsView.as_view(), name='system_stats'),
        path('email-logs/', views.EmailLogsView.as_view(), name='email_logs'),
        path('platform-settings/', views.PlatformSettingsView.as_view(), name='platform_settings'),
    ])),
    
    # API endpoints for AJAX calls
    path('ajax/', include([
        path('contact-count/', views.ContactCountAjaxView.as_view(), name='contact_count_ajax'),
        path('campaign-stats/', views.CampaignStatsAjaxView.as_view(), name='campaign_stats_ajax'),
        path('email-test/', views.EmailTestAjaxView.as_view(), name='email_test_ajax'),
        path('domain-verify/', views.DomainVerifyAjaxView.as_view(), name='domain_verify_ajax'),
    ])),
]
