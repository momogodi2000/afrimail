# backend/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    CustomUser, UserProfile, UserActivity,
    Contact, ContactList, ContactTag, ContactImport,
    EmailDomainConfig, EmailTemplate, EmailCampaign, EmailQueue,
    EmailEvent, CampaignAnalytics, ContactEngagement, PlatformAnalytics
)
import json


# Custom Admin Site
class AfriMailAdminSite(admin.AdminSite):
    site_header = "AfriMail Pro Administration"
    site_title = "AfriMail Pro Admin"
    index_title = "Welcome to AfriMail Pro Administration"
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard with statistics"""
        extra_context = extra_context or {}
        
        # Get basic statistics
        extra_context.update({
            'total_users': CustomUser.objects.filter(is_active=True).count(),
            'total_contacts': Contact.objects.filter(is_active=True).count(),
            'total_campaigns': EmailCampaign.objects.count(),
            'active_campaigns': EmailCampaign.objects.filter(status='SENDING').count(),
            'emails_sent_today': EmailEvent.objects.filter(
                event_type='SENT',
                created_at__date=timezone.now().date()
            ).count(),
        })
        
        return super().index(request, extra_context)


# Replace default admin site
admin_site = AfriMailAdminSite(name='afrimail_admin')


@admin.register(CustomUser, site=admin_site)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User Admin"""
    
    list_display = [
        'email', 'get_full_name', 'company', 'role', 'country', 
        'is_active', 'is_email_verified', 'login_count', 'last_login'
    ]
    list_filter = [
        'role', 'is_active', 'is_email_verified', 'country', 
        'industry', 'company_size', 'date_joined'
    ]
    search_fields = ['email', 'first_name', 'last_name', 'company']
    readonly_fields = [
        'id', 'date_joined', 'last_login', 'login_count', 
        'email_verification_token', 'password_reset_token'
    ]
    
    fieldsets = (
        ('Account Information', {
            'fields': ('id', 'email', 'password', 'role')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone')
        }),
        ('Company Information', {
            'fields': ('company', 'company_website', 'industry', 'company_size')
        }),
        ('Location', {
            'fields': ('country', 'city')
        }),
        ('Account Status', {
            'fields': ('is_active', 'is_email_verified', 'is_staff', 'is_superuser')
        }),
        ('Usage Statistics', {
            'fields': ('login_count', 'last_login', 'last_login_ip')
        }),
        ('Preferences', {
            'fields': ('preferred_language', 'timezone', 'receive_notifications')
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'created_at', 'updated_at')
        }),
    )
    
    add_fieldsets = (
        ('Account Information', {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'company')
        }),
    )
    
    ordering = ['-date_joined']
    filter_horizontal = []
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Name'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile')
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of super admins
        if obj and obj.is_super_admin:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(UserProfile, site=admin_site)
class UserProfileAdmin(admin.ModelAdmin):
    """User Profile Admin"""
    
    list_display = [
        'user', 'total_contacts', 'total_campaigns', 'total_emails_sent',
        'max_contacts', 'is_trial', 'trial_end_date'
    ]
    list_filter = ['is_trial', 'email_marketing_consent', 'newsletter_subscription']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['total_contacts', 'total_campaigns', 'total_emails_sent']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Profile Information', {
            'fields': ('avatar', 'bio')
        }),
        ('Marketing Preferences', {
            'fields': ('email_marketing_consent', 'newsletter_subscription')
        }),
        ('Platform Settings', {
            'fields': ('dashboard_layout', 'items_per_page', 'email_signature')
        }),
        ('Usage Statistics', {
            'fields': ('total_contacts', 'total_campaigns', 'total_emails_sent')
        }),
        ('Account Limits', {
            'fields': ('max_contacts', 'max_campaigns_per_month', 'max_emails_per_month')
        }),
        ('Trial & Billing', {
            'fields': ('is_trial', 'trial_end_date')
        }),
    )


@admin.register(UserActivity, site=admin_site)
class UserActivityAdmin(admin.ModelAdmin):
    """User Activity Admin"""
    
    list_display = ['user', 'activity_type', 'description', 'ip_address', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['user__email', 'activity_type', 'description']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Contact, site=admin_site)
class ContactAdmin(admin.ModelAdmin):
    """Contact Admin"""
    
    list_display = [
        'email', 'get_full_name', 'company', 'user', 'status',
        'engagement_score', 'total_emails_received', 'created_at'
    ]
    list_filter = [
        'status', 'user', 'country', 'gender', 'created_at',
        'is_active', 'source'
    ]
    search_fields = ['email', 'first_name', 'last_name', 'company']
    readonly_fields = [
        'id', 'engagement_score', 'total_emails_received',
        'total_emails_opened', 'total_emails_clicked', 'created_at', 'updated_at'
    ]
    filter_horizontal = ['lists', 'tags']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'email', 'first_name', 'last_name')
        }),
        ('Personal Details', {
            'fields': ('phone', 'gender', 'date_of_birth')
        }),
        ('Address Information', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Professional Information', {
            'fields': ('company', 'job_title', 'industry', 'website')
        }),
        ('Contact Status', {
            'fields': ('status', 'is_active')
        }),
        ('Subscription Management', {
            'fields': ('subscribed_at', 'unsubscribed_at', 'unsubscribe_reason')
        }),
        ('Lists and Tags', {
            'fields': ('lists', 'tags')
        }),
        ('Engagement Metrics', {
            'fields': (
                'engagement_score', 'total_emails_received',
                'total_emails_opened', 'total_emails_clicked',
                'last_email_opened_at', 'last_email_clicked_at'
            )
        }),
        ('Source Tracking', {
            'fields': ('source', 'referrer', 'utm_source', 'utm_medium', 'utm_campaign')
        }),
        ('Custom Fields', {
            'fields': ('custom_fields',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Name'


@admin.register(ContactList, site=admin_site)
class ContactListAdmin(admin.ModelAdmin):
    """Contact List Admin"""
    
    list_display = [
        'name', 'user', 'list_type', 'contact_count',
        'is_active', 'is_favorite', 'created_at'
    ]
    list_filter = ['list_type', 'is_active', 'is_favorite', 'user', 'created_at']
    search_fields = ['name', 'description', 'user__email']
    readonly_fields = ['id', 'contact_count', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(ContactTag, site=admin_site)
class ContactTagAdmin(admin.ModelAdmin):
    """Contact Tag Admin"""
    
    list_display = ['name', 'user', 'color', 'contact_count', 'created_at']
    list_filter = ['user', 'created_at']
    search_fields = ['name', 'description', 'user__email']
    
    def contact_count(self, obj):
        return obj.contacts.count()
    contact_count.short_description = 'Contacts'


@admin.register(EmailDomainConfig, site=admin_site)
class EmailDomainConfigAdmin(admin.ModelAdmin):
    """Email Domain Configuration Admin"""
    
    list_display = [
        'domain_name', 'from_email', 'user', 'smtp_provider',
        'domain_verified', 'is_default', 'is_active'
    ]
    list_filter = [
        'smtp_provider', 'domain_verified', 'is_default',
        'is_active', 'user', 'created_at'
    ]
    search_fields = ['domain_name', 'from_email', 'user__email']
    readonly_fields = [
        'id', 'verification_token', 'verification_attempts',
        'last_verification_attempt', 'emails_sent_today',
        'emails_sent_this_month', 'last_used_at', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Domain Information', {
            'fields': ('id', 'user', 'domain_name', 'from_email', 'from_name', 'reply_to_email')
        }),
        ('SMTP Configuration', {
            'fields': (
                'smtp_provider', 'smtp_host', 'smtp_port',
                'smtp_username', 'smtp_password', 'use_tls', 'use_ssl'
            )
        }),
        ('Domain Verification', {
            'fields': (
                'domain_verified', 'verification_status', 'verification_token',
                'verification_attempts', 'last_verification_attempt'
            )
        }),
        ('DNS Records', {
            'fields': ('spf_record', 'dkim_record', 'dmarc_record')
        }),
        ('Usage Settings', {
            'fields': ('is_default', 'is_active', 'daily_send_limit', 'monthly_send_limit')
        }),
        ('Usage Tracking', {
            'fields': ('emails_sent_today', 'emails_sent_this_month', 'last_used_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(EmailTemplate, site=admin_site)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Email Template Admin"""
    
    list_display = [
        'name', 'user', 'template_type', 'usage_count',
        'is_active', 'is_shared', 'last_used_at'
    ]
    list_filter = ['template_type', 'is_active', 'is_shared', 'user', 'created_at']
    search_fields = ['name', 'description', 'subject', 'user__email']
    readonly_fields = ['id', 'usage_count', 'last_used_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Template Information', {
            'fields': ('id', 'user', 'name', 'description', 'template_type')
        }),
        ('Email Content', {
            'fields': ('subject', 'html_content', 'text_content')
        }),
        ('Template Settings', {
            'fields': ('is_active', 'is_shared')
        }),
        ('Usage Tracking', {
            'fields': ('usage_count', 'last_used_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(EmailCampaign, site=admin_site)
class EmailCampaignAdmin(admin.ModelAdmin):
    """Email Campaign Admin"""
    
    list_display = [
        'name', 'user', 'status', 'campaign_type', 'recipient_count',
        'emails_sent', 'open_rate_display', 'click_rate_display', 'created_at'
    ]
    list_filter = [
        'status', 'campaign_type', 'priority', 'user',
        'track_opens', 'track_clicks', 'created_at'
    ]
    search_fields = ['name', 'subject', 'user__email']
    readonly_fields = [
        'id', 'recipient_count', 'emails_sent', 'emails_delivered',
        'emails_bounced', 'emails_failed', 'unique_opens', 'total_opens',
        'unique_clicks', 'total_clicks', 'unsubscribes', 'complaints',
        'open_rate', 'click_rate', 'bounce_rate', 'unsubscribe_rate',
        'created_at', 'updated_at', 'started_at', 'completed_at'
    ]
    filter_horizontal = ['contact_lists']
    
    fieldsets = (
        ('Campaign Information', {
            'fields': ('id', 'user', 'name', 'description', 'campaign_type')
        }),
        ('Email Configuration', {
            'fields': ('email_config', 'template')
        }),
        ('Email Content', {
            'fields': ('subject', 'from_name', 'from_email', 'reply_to_email', 'html_content', 'text_content')
        }),
        ('Recipients', {
            'fields': ('contact_lists', 'recipient_count')
        }),
        ('Scheduling', {
            'fields': ('status', 'priority', 'scheduled_at', 'send_immediately')
        }),
        ('Campaign Settings', {
            'fields': ('track_opens', 'track_clicks', 'track_unsubscribes')
        }),
        ('Sending Progress', {
            'fields': ('emails_sent', 'emails_delivered', 'emails_bounced', 'emails_failed')
        }),
        ('Analytics', {
            'fields': (
                'unique_opens', 'total_opens', 'unique_clicks', 'total_clicks',
                'unsubscribes', 'complaints', 'open_rate', 'click_rate',
                'bounce_rate', 'unsubscribe_rate'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'started_at', 'completed_at')
        }),
    )
    
    def open_rate_display(self, obj):
        return f"{obj.open_rate:.1f}%"
    open_rate_display.short_description = 'Open Rate'
    
    def click_rate_display(self, obj):
        return f"{obj.click_rate:.1f}%"
    click_rate_display.short_description = 'Click Rate'
    
    actions = ['duplicate_campaigns']
    
    def duplicate_campaigns(self, request, queryset):
        """Duplicate selected campaigns"""
        duplicated = 0
        for campaign in queryset:
            campaign.duplicate(f"Copy of {campaign.name}")
            duplicated += 1
        
        self.message_user(request, f"Successfully duplicated {duplicated} campaigns.")
    duplicate_campaigns.short_description = "Duplicate selected campaigns"


@admin.register(EmailEvent, site=admin_site)
class EmailEventAdmin(admin.ModelAdmin):
    """Email Event Admin"""
    
    list_display = [
        'campaign', 'contact', 'event_type', 'ip_address',
        'country', 'created_at'
    ]
    list_filter = ['event_type', 'bounce_type', 'country', 'created_at']
    search_fields = [
        'campaign__name', 'contact__email', 'ip_address',
        'clicked_url', 'bounce_reason'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CampaignAnalytics, site=admin_site)
class CampaignAnalyticsAdmin(admin.ModelAdmin):
    """Campaign Analytics Admin"""
    
    list_display = [
        'campaign', 'date', 'emails_sent', 'delivery_rate_display',
        'open_rate_display', 'click_rate_display'
    ]
    list_filter = ['date', 'campaign__user']
    search_fields = ['campaign__name']
    readonly_fields = [
        'delivery_rate', 'open_rate', 'click_rate',
        'unsubscribe_rate', 'bounce_rate', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    
    def delivery_rate_display(self, obj):
        return f"{obj.delivery_rate:.1f}%"
    delivery_rate_display.short_description = 'Delivery Rate'
    
    def open_rate_display(self, obj):
        return f"{obj.open_rate:.1f}%"
    open_rate_display.short_description = 'Open Rate'
    
    def click_rate_display(self, obj):
        return f"{obj.click_rate:.1f}%"
    click_rate_display.short_description = 'Click Rate'


@admin.register(PlatformAnalytics, site=admin_site)
class PlatformAnalyticsAdmin(admin.ModelAdmin):
    """Platform Analytics Admin"""
    
    list_display = [
        'date', 'total_users', 'active_users', 'new_users_today',
        'emails_sent_today', 'average_delivery_rate_display'
    ]
    list_filter = ['date']
    readonly_fields = [
        'total_users', 'active_users', 'new_users_today',
        'total_contacts', 'total_campaigns', 'total_templates',
        'emails_sent_today', 'emails_delivered_today',
        'emails_opened_today', 'emails_clicked_today',
        'average_delivery_rate', 'average_open_rate', 'average_click_rate',
        'api_requests_today', 'failed_requests_today', 'average_response_time',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    
    def average_delivery_rate_display(self, obj):
        return f"{obj.average_delivery_rate:.1f}%"
    average_delivery_rate_display.short_description = 'Avg Delivery Rate'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# Inline Admins
class ContactListInline(admin.TabularInline):
    model = ContactList
    extra = 0
    readonly_fields = ['contact_count']


class EmailDomainConfigInline(admin.TabularInline):
    model = EmailDomainConfig
    extra = 0
    readonly_fields = ['domain_verified', 'emails_sent_today']


class UserActivityInline(admin.TabularInline):
    model = UserActivity
    extra = 0
    readonly_fields = ['activity_type', 'created_at']
    
    def has_add_permission(self, request, obj=None):
        return False


# Add inlines to User admin
CustomUserAdmin.inlines = [UserActivityInline, ContactListInline, EmailDomainConfigInline]


# Custom admin actions
@admin.action(description='Verify email for selected users')
def verify_user_emails(modeladmin, request, queryset):
    """Verify email for selected users"""
    updated = 0
    for user in queryset:
        if not user.is_email_verified:
            user.verify_email()
            updated += 1
    
    modeladmin.message_user(
        request,
        f"Successfully verified emails for {updated} users."
    )


@admin.action(description='Activate selected users')
def activate_users(modeladmin, request, queryset):
    """Activate selected users"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(
        request,
        f"Successfully activated {updated} users."
    )


@admin.action(description='Deactivate selected users')
def deactivate_users(modeladmin, request, queryset):
    """Deactivate selected users"""
    # Prevent deactivating super admins
    queryset = queryset.exclude(role='SUPER_ADMIN')
    updated = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f"Successfully deactivated {updated} users."
    )


# Add actions to User admin
CustomUserAdmin.actions = [verify_user_emails, activate_users, deactivate_users]


# Register remaining models
admin_site.register(admin.models.LogEntry)

# Customize admin site
admin.site = admin_site