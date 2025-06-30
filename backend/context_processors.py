

# backend/context_processors.py

from django.conf import settings
from django.utils import timezone
from .models import UserProfile, EmailDomainConfig, ContactList
from .authentication import PermissionManager
import logging

logger = logging.getLogger(__name__)


def global_context(request):
    """
    Global context processor for AfriMail Pro
    """
    context = {
        'PLATFORM_NAME': getattr(settings, 'PLATFORM_NAME', 'AfriMail Pro'),
        'DEBUG': settings.DEBUG,
        'current_year': timezone.now().year,
        'current_time': timezone.now(),
        'pwa_enabled': True,
        'hot_reload_enabled': settings.DEBUG,
    }
    
    # Add user-specific context
    if request.user.is_authenticated:
        try:
            # User profile
            profile = getattr(request.user, 'profile', None)
            if profile:
                context.update({
                    'user_profile': profile,
                    'user_avatar': profile.avatar.url if profile.avatar else None,
                    'user_can_create_contact': profile.can_create_contact(),
                    'user_can_create_campaign': profile.can_create_campaign(),
                })
            
            # User permissions
            context['user_permissions'] = PermissionManager.get_user_permissions(request.user)
            
            # Quick stats for dashboard
            context.update({
                'total_contacts': request.user.contacts.filter(is_active=True).count(),
                'total_campaigns': request.user.email_campaigns.count(),
                'total_contact_lists': request.user.contact_lists.filter(is_active=True).count(),
                'total_email_configs': request.user.email_domains.filter(is_active=True).count(),
            })
            
            # Navigation items based on user role
            context['nav_items'] = _get_navigation_items(request.user)
            
            # Recent activity (last 5 activities)
            context['recent_activities'] = request.user.activities.all()[:5]
            
            # Email configuration status
            context['has_email_config'] = request.user.email_domains.filter(
                is_active=True,
                domain_verified=True
            ).exists()
            
        except Exception as e:
            logger.error(f"Context processor error: {str(e)}")
    
    # Add system-wide context
    try:
        # System status
        context['system_status'] = _get_system_status()
        
        # Featured contact lists (if any)
        if request.user.is_authenticated:
            context['featured_lists'] = request.user.contact_lists.filter(
                is_favorite=True,
                is_active=True
            )[:3]
        
        # Maintenance mode status
        from django.core.cache import cache
        context['maintenance_mode'] = cache.get('maintenance_mode', False)
        
    except Exception as e:
        logger.error(f"System context error: {str(e)}")
    
    return context


def _get_navigation_items(user):
    """Get navigation items based on user role"""
    nav_items = [
        {
            'name': 'Dashboard',
            'url': 'backend:dashboard',
            'icon': 'dashboard',
            'permission': 'view_dashboard'
        },
        {
            'name': 'Contacts',
            'url': 'backend:contact_list',
            'icon': 'contacts',
            'permission': 'manage_contacts',
            'children': [
                {'name': 'All Contacts', 'url': 'backend:contact_list'},
                {'name': 'Contact Lists', 'url': 'backend:contact_lists'},
                {'name': 'Import Contacts', 'url': 'backend:contact_import'},
            ]
        },
        {
            'name': 'Campaigns',
            'url': 'backend:campaign_list',
            'icon': 'campaigns',
            'permission': 'create_campaigns',
            'children': [
                {'name': 'All Campaigns', 'url': 'backend:campaign_list'},
                {'name': 'Create Campaign', 'url': 'backend:campaign_create'},
                {'name': 'Templates', 'url': 'backend:template_list'},
            ]
        },
        {
            'name': 'Analytics',
            'url': 'backend:analytics_overview',
            'icon': 'analytics',
            'permission': 'view_analytics',
            'children': [
                {'name': 'Overview', 'url': 'backend:analytics_overview'},
                {'name': 'Campaign Analytics', 'url': 'backend:campaign_analytics_list'},
                {'name': 'Contact Analytics', 'url': 'backend:contact_analytics'},
                {'name': 'Reports', 'url': 'backend:reports'},
            ]
        },
        {
            'name': 'Email Config',
            'url': 'backend:email_config_list',
            'icon': 'email-config',
            'permission': 'manage_email_config',
        },
    ]
    
    # Add admin navigation for super admins
    if user.is_super_admin:
        nav_items.append({
            'name': 'Admin Panel',
            'url': 'backend:admin_dashboard',
            'icon': 'admin',
            'permission': 'access_admin_panel',
            'children': [
                {'name': 'Dashboard', 'url': 'backend:admin_dashboard'},
                {'name': 'Users', 'url': 'backend:admin_user_list'},
                {'name': 'System Stats', 'url': 'backend:system_stats'},
                {'name': 'Email Logs', 'url': 'backend:email_logs'},
                {'name': 'Platform Settings', 'url': 'backend:platform_settings'},
            ]
        })
    
    # Filter navigation based on permissions
    user_permissions = PermissionManager.get_user_permissions(user)
    filtered_nav = []
    
    for item in nav_items:
        if item.get('permission') in user_permissions:
            filtered_nav.append(item)
    
    return filtered_nav


def _get_system_status():
    """Get system status information"""
    try:
        from django.core.cache import cache
        from django.db import connection
        
        status = {
            'database_connected': True,
            'cache_connected': True,
            'email_service_status': 'active',
            'last_updated': timezone.now(),
        }
        
        # Test database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            status['database_connected'] = False
        
        # Test cache connection
        try:
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') != 'ok':
                status['cache_connected'] = False
        except Exception:
            status['cache_connected'] = False
        
        # Overall health
        status['healthy'] = all([
            status['database_connected'],
            status['cache_connected'],
        ])
        
        return status
        
    except Exception as e:
        logger.error(f"System status check error: {str(e)}")
        return {
            'healthy': False,
            'error': str(e),
            'last_updated': timezone.now(),
        }


def dashboard_context(request):
    """
    Context processor specifically for dashboard pages
    """
    if not request.user.is_authenticated:
        return {}
    
    try:
        context = {}
        
        # Quick statistics
        if request.user.is_super_admin:
            # Admin dashboard context
            from .models import CustomUser, EmailCampaign, Contact
            context.update({
                'total_users': CustomUser.objects.filter(is_active=True).count(),
                'total_campaigns_platform': EmailCampaign.objects.count(),
                'total_contacts_platform': Contact.objects.filter(is_active=True).count(),
                'active_campaigns': EmailCampaign.objects.filter(status='SENDING').count(),
            })
        else:
            # Client dashboard context
            context.update({
                'recent_campaigns': request.user.email_campaigns.all()[:5],
                'top_performing_campaigns': request.user.email_campaigns.filter(
                    status='SENT'
                ).order_by('-open_rate')[:3],
                'engagement_score': _calculate_user_engagement_score(request.user),
            })
        
        return context
        
    except Exception as e:
        logger.error(f"Dashboard context error: {str(e)}")
        return {}


def _calculate_user_engagement_score(user):
    """Calculate overall engagement score for user"""
    try:
        campaigns = user.email_campaigns.filter(status='SENT')
        if not campaigns.exists():
            return 0
        
        total_open_rate = sum([c.open_rate for c in campaigns])
        total_click_rate = sum([c.click_rate for c in campaigns])
        
        avg_open_rate = total_open_rate / campaigns.count()
        avg_click_rate = total_click_rate / campaigns.count()
        
        # Weighted engagement score
        engagement_score = (avg_open_rate * 0.6) + (avg_click_rate * 0.4)
        return round(engagement_score, 1)
        
    except Exception as e:
        logger.error(f"Engagement score calculation error: {str(e)}")
        return 0