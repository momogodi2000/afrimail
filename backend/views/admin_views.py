# backend/views/admin_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Avg, Q
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from django.core.cache import cache
import json
import csv
import logging
from datetime import timedelta, date

from ..models import (
    CustomUser, UserProfile, Contact, ContactList, EmailCampaign,
    EmailEvent, EmailDomainConfig, PlatformAnalytics, UserActivity,
    CampaignAnalytics, ApiUsage
)
from ..services.analytics_service import AnalyticsService
from ..authentication import PermissionManager

logger = logging.getLogger(__name__)


def is_super_admin(user):
    """Check if user is super admin"""
    return user.is_authenticated and user.is_super_admin


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class AdminDashboardView(TemplateView):
    """Super Admin dashboard"""
    
    template_name = 'admin/admin_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get platform-wide statistics
        analytics_service = AnalyticsService()
        platform_analytics = analytics_service.get_platform_analytics(30)
        
        context['platform_analytics'] = platform_analytics
        
        # Quick stats
        context['quick_stats'] = {
            'total_users': CustomUser.objects.filter(is_active=True).count(),
            'total_campaigns': EmailCampaign.objects.count(),
            'total_contacts': Contact.objects.filter(is_active=True).count(),
            'emails_sent_today': EmailEvent.objects.filter(
                event_type='SENT',
                created_at__date=timezone.now().date()
            ).count(),
            'active_campaigns': EmailCampaign.objects.filter(status='SENDING').count(),
            'failed_campaigns': EmailCampaign.objects.filter(status='FAILED').count(),
        }
        
        # Recent activity
        context['recent_users'] = CustomUser.objects.filter(
            role='CLIENT',
            is_active=True
        ).order_by('-date_joined')[:5]
        
        context['recent_campaigns'] = EmailCampaign.objects.select_related('user').order_by('-created_at')[:10]
        
        # System health
        context['system_health'] = self._get_system_health()
        
        # Top performing users
        context['top_users'] = self._get_top_users()
        
        return context
    
    def _get_system_health(self):
        """Get system health indicators"""
        try:
            # Database check
            db_healthy = True
            try:
                CustomUser.objects.count()
            except:
                db_healthy = False
            
            # Cache check
            cache_healthy = True
            try:
                cache.set('health_check', 'ok', 10)
                cache_healthy = cache.get('health_check') == 'ok'
            except:
                cache_healthy = False
            
            # Recent errors check
            recent_failures = EmailCampaign.objects.filter(
                status='FAILED',
                updated_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            return {
                'database': db_healthy,
                'cache': cache_healthy,
                'recent_failures': recent_failures,
                'overall_healthy': db_healthy and cache_healthy and recent_failures < 10,
            }
        except Exception as e:
            logger.error(f"System health check error: {str(e)}")
            return {'overall_healthy': False, 'error': str(e)}
    
    def _get_top_users(self):
        """Get top performing users by email volume"""
        return CustomUser.objects.filter(
            role='CLIENT',
            is_active=True
        ).annotate(
            total_emails_sent=Sum('email_campaigns__emails_sent'),
            total_campaigns=Count('email_campaigns')
        ).order_by('-total_emails_sent')[:10]


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class AdminUserListView(ListView):
    """List all users for admin management"""
    
    model = CustomUser
    template_name = 'admin/user_list.html'
    context_object_name = 'users'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = CustomUser.objects.all().order_by('-date_joined')
        
        # Apply filters
        role_filter = self.request.GET.get('role')
        status_filter = self.request.GET.get('status')
        search = self.request.GET.get('search')
        
        if role_filter:
            queryset = queryset.filter(role=role_filter)
        
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        elif status_filter == 'unverified':
            queryset = queryset.filter(is_email_verified=False)
        
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(company__icontains=search)
            )
        
        return queryset.select_related('profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['filters'] = {
            'role': self.request.GET.get('role', ''),
            'status': self.request.GET.get('status', ''),
            'search': self.request.GET.get('search', ''),
        }
        
        # Add summary stats
        all_users = CustomUser.objects.all()
        context['user_stats'] = {
            'total_users': all_users.count(),
            'active_users': all_users.filter(is_active=True).count(),
            'super_admins': all_users.filter(role='SUPER_ADMIN').count(),
            'client_users': all_users.filter(role='CLIENT').count(),
            'unverified_users': all_users.filter(is_email_verified=False).count(),
            'new_users_today': all_users.filter(date_joined__date=timezone.now().date()).count(),
        }
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class AdminUserDetailView(DetailView):
    """Detailed view of a user for admin"""
    
    model = CustomUser
    template_name = 'admin/user_detail.html'
    context_object_name = 'user_obj'  # Avoid conflict with request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = self.object
        
        # Get user statistics
        context['user_stats'] = {
            'total_contacts': user_obj.contacts.filter(is_active=True).count(),
            'total_campaigns': user_obj.email_campaigns.count(),
            'total_emails_sent': user_obj.email_campaigns.aggregate(
                total=Sum('emails_sent')
            )['total'] or 0,
            'avg_open_rate': self._calculate_avg_open_rate(user_obj),
            'avg_click_rate': self._calculate_avg_click_rate(user_obj),
            'email_domains': user_obj.email_domains.filter(is_active=True).count(),
        }
        
        # Recent activity
        context['recent_activities'] = UserActivity.objects.filter(
            user=user_obj
        ).order_by('-created_at')[:20]
        
        # Recent campaigns
        context['recent_campaigns'] = user_obj.email_campaigns.order_by('-created_at')[:10]
        
        # Account usage vs limits
        profile = getattr(user_obj, 'profile', None)
        if profile:
            context['usage_info'] = {
                'contacts_used': context['user_stats']['total_contacts'],
                'contacts_limit': profile.max_contacts,
                'campaigns_this_month': user_obj.email_campaigns.filter(
                    created_at__month=timezone.now().month,
                    created_at__year=timezone.now().year
                ).count(),
                'campaigns_limit': profile.max_campaigns_per_month,
            }
        
        return context
    
    def _calculate_avg_open_rate(self, user):
        """Calculate average open rate for user"""
        campaigns = user.email_campaigns.filter(status='SENT', emails_delivered__gt=0)
        if not campaigns.exists():
            return 0
        return sum([c.open_rate for c in campaigns]) / campaigns.count()
    
    def _calculate_avg_click_rate(self, user):
        """Calculate average click rate for user"""
        campaigns = user.email_campaigns.filter(status='SENT', emails_delivered__gt=0)
        if not campaigns.exists():
            return 0
        return sum([c.click_rate for c in campaigns]) / campaigns.count()


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class AdminUserUpdateView(UpdateView):
    """Update user details (admin only)"""
    
    model = CustomUser
    template_name = 'admin/user_update.html'
    fields = [
        'first_name', 'last_name', 'email', 'company', 'phone',
        'country', 'city', 'industry', 'company_size', 'role',
        'is_active', 'is_email_verified', 'receive_notifications'
    ]
    
    def form_valid(self, form):
        user_obj = form.save()
        
        # Log admin action
        UserActivity.log_activity(
            user=user_obj,
            activity_type='ADMIN_USER_UPDATED',
            description=f'User updated by admin {self.request.user.email}',
            request=self.request,
            metadata={'admin_user': self.request.user.email}
        )
        
        messages.success(self.request, f'User "{user_obj.get_full_name()}" updated successfully!')
        return redirect('backend:admin_user_detail', pk=user_obj.pk)


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class AdminUserDeleteView(View):
    """Deactivate user (admin only)"""
    
    def post(self, request, pk):
        user_obj = get_object_or_404(CustomUser, pk=pk)
        
        # Prevent deleting super admins
        if user_obj.is_super_admin:
            messages.error(request, 'Cannot deactivate super admin users.')
            return redirect('backend:admin_user_detail', pk=pk)
        
        # Soft delete - deactivate instead of delete
        user_obj.is_active = False
        user_obj.save()
        
        # Log admin action
        UserActivity.log_activity(
            user=user_obj,
            activity_type='ADMIN_USER_DEACTIVATED',
            description=f'User deactivated by admin {request.user.email}',
            request=request,
            metadata={'admin_user': request.user.email}
        )
        
        messages.success(request, f'User "{user_obj.get_full_name()}" deactivated successfully!')
        return redirect('backend:admin_user_list')


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class SystemStatsView(TemplateView):
    """System-wide statistics and monitoring"""
    
    template_name = 'admin/system_stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range
        days = int(self.request.GET.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Platform analytics
        analytics_service = AnalyticsService()
        context['platform_analytics'] = analytics_service.get_platform_analytics(days)
        
        # Email statistics
        context['email_stats'] = self._get_email_statistics(start_date, end_date)
        
        # User statistics
        context['user_stats'] = self._get_user_statistics(start_date, end_date)
        
        # Performance metrics
        context['performance_metrics'] = self._get_performance_metrics(start_date, end_date)
        
        # Growth trends
        context['growth_trends'] = self._get_growth_trends(days)
        
        # System usage
        context['system_usage'] = self._get_system_usage()
        
        context['days'] = days
        
        return context
    
    def _get_email_statistics(self, start_date, end_date):
        """Get email statistics for date range"""
        events = EmailEvent.objects.filter(created_at__range=[start_date, end_date])
        
        return {
            'total_sent': events.filter(event_type='SENT').count(),
            'total_delivered': events.filter(event_type='DELIVERED').count(),
            'total_opened': events.filter(event_type='OPENED').count(),
            'total_clicked': events.filter(event_type='CLICKED').count(),
            'total_bounced': events.filter(event_type='BOUNCED').count(),
            'total_unsubscribed': events.filter(event_type='UNSUBSCRIBED').count(),
            'total_complained': events.filter(event_type='COMPLAINED').count(),
        }
    
    def _get_user_statistics(self, start_date, end_date):
        """Get user statistics for date range"""
        return {
            'new_users': CustomUser.objects.filter(
                date_joined__range=[start_date, end_date]
            ).count(),
            'active_users': CustomUser.objects.filter(
                last_login__range=[start_date, end_date]
            ).count(),
            'users_with_campaigns': CustomUser.objects.filter(
                email_campaigns__created_at__range=[start_date, end_date]
            ).distinct().count(),
            'users_with_emails_sent': CustomUser.objects.filter(
                email_campaigns__events__event_type='SENT',
                email_campaigns__events__created_at__range=[start_date, end_date]
            ).distinct().count(),
        }
    
    def _get_performance_metrics(self, start_date, end_date):
        """Get performance metrics"""
        campaigns = EmailCampaign.objects.filter(
            status='SENT',
            completed_at__range=[start_date, end_date]
        )
        
        if not campaigns.exists():
            return {
                'avg_delivery_rate': 0,
                'avg_open_rate': 0,
                'avg_click_rate': 0,
                'avg_unsubscribe_rate': 0,
            }
        
        return {
            'avg_delivery_rate': campaigns.aggregate(
                avg=Avg('emails_delivered') * 100 / Avg('emails_sent')
            )['avg'] or 0,
            'avg_open_rate': sum([c.open_rate for c in campaigns]) / campaigns.count(),
            'avg_click_rate': sum([c.click_rate for c in campaigns]) / campaigns.count(),
            'avg_unsubscribe_rate': sum([c.unsubscribe_rate for c in campaigns]) / campaigns.count(),
        }
    
    def _get_growth_trends(self, days):
        """Get growth trends over time"""
        trends = []
        
        for i in range(days):
            date_obj = timezone.now().date() - timedelta(days=i)
            
            trends.append({
                'date': date_obj.isoformat(),
                'new_users': CustomUser.objects.filter(date_joined__date=date_obj).count(),
                'new_campaigns': EmailCampaign.objects.filter(created_at__date=date_obj).count(),
                'emails_sent': EmailEvent.objects.filter(
                    event_type='SENT',
                    created_at__date=date_obj
                ).count(),
            })
        
        return list(reversed(trends))
    
    def _get_system_usage(self):
        """Get system usage metrics"""
        return {
            'total_storage_mb': self._calculate_storage_usage(),
            'database_size_mb': self._get_database_size(),
            'active_domains': EmailDomainConfig.objects.filter(
                is_active=True,
                domain_verified=True
            ).count(),
            'failed_domains': EmailDomainConfig.objects.filter(
                is_active=True,
                domain_verified=False
            ).count(),
        }
    
    def _calculate_storage_usage(self):
        """Calculate approximate storage usage in MB"""
        # This is a simplified calculation
        # In production, you'd want more accurate disk usage metrics
        total_contacts = Contact.objects.count()
        total_campaigns = EmailCampaign.objects.count()
        total_events = EmailEvent.objects.count()
        
        # Rough estimation: 1KB per contact, 5KB per campaign, 0.5KB per event
        estimated_mb = (total_contacts + (total_campaigns * 5) + (total_events * 0.5)) / 1024
        return round(estimated_mb, 2)
    
    def _get_database_size(self):
        """Get database size (simplified)"""
        # This would need to be implemented based on your database type
        # For now, return a placeholder
        return 0


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class EmailLogsView(ListView):
    """View email logs and events"""
    
    model = EmailEvent
    template_name = 'admin/email_logs.html'
    context_object_name = 'events'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = EmailEvent.objects.select_related(
            'campaign', 'contact', 'campaign__user'
        ).order_by('-created_at')
        
        # Apply filters
        event_type = self.request.GET.get('event_type')
        user_id = self.request.GET.get('user_id')
        campaign_id = self.request.GET.get('campaign_id')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        if user_id:
            queryset = queryset.filter(campaign__user_id=user_id)
        
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['event_types'] = EmailEvent.EVENT_TYPES
        context['users'] = CustomUser.objects.filter(
            role='CLIENT',
            is_active=True
        ).order_by('first_name', 'last_name')
        
        context['filters'] = {
            'event_type': self.request.GET.get('event_type', ''),
            'user_id': self.request.GET.get('user_id', ''),
            'campaign_id': self.request.GET.get('campaign_id', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }
        
        # Add event summary
        context['event_summary'] = EmailEvent.objects.filter(
            created_at__date=timezone.now().date()
        ).values('event_type').annotate(count=Count('id'))
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class PlatformSettingsView(TemplateView):
    """Manage platform-wide settings"""
    
    template_name = 'admin/platform_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current settings from cache
        context['settings'] = {
            'platform_name': cache.get('platform_platform_name', 'AfriMail Pro'),
            'platform_tagline': cache.get('platform_platform_tagline', 'Connectez l\'Afrique, Un Email à la Fois'),
            'support_email': cache.get('platform_support_email', 'support@afrimailpro.com'),
            'max_contacts_default': cache.get('platform_max_contacts_default', 10000),
            'max_campaigns_default': cache.get('platform_max_campaigns_default', 100),
            'max_emails_default': cache.get('platform_max_emails_default', 50000),
            'email_verification_required': cache.get('platform_email_verification_required', True),
            'maintenance_mode': cache.get('platform_maintenance_mode', False),
        }
        
        return context
    
    def post(self, request):
        """Update platform settings"""
        try:
            # Update settings in cache
            settings_to_update = [
                'platform_name', 'platform_tagline', 'support_email',
                'max_contacts_default', 'max_campaigns_default', 'max_emails_default'
            ]
            
            for setting in settings_to_update:
                value = request.POST.get(setting)
                if value:
                    cache.set(f'platform_{setting}', value, 86400 * 30)  # 30 days
            
            # Handle boolean settings
            cache.set('platform_email_verification_required', 
                     request.POST.get('email_verification_required') == 'on', 86400 * 30)
            cache.set('platform_maintenance_mode', 
                     request.POST.get('maintenance_mode') == 'on', 86400 * 30)
            
            # Log admin action
            UserActivity.log_activity(
                user=request.user,
                activity_type='PLATFORM_SETTINGS_UPDATED',
                description='Platform settings updated',
                request=request
            )
            
            messages.success(request, 'Platform settings updated successfully!')
            
        except Exception as e:
            logger.error(f"Platform settings update error: {str(e)}")
            messages.error(request, 'Failed to update platform settings.')
        
        return redirect('backend:platform_settings')


# AJAX Views for Admin Panel
@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class AdminQuickStatsView(View):
    """Get quick stats for admin dashboard"""
    
    def get(self, request):
        try:
            stats = {
                'users_online': CustomUser.objects.filter(
                    last_login__gte=timezone.now() - timedelta(minutes=15)
                ).count(),
                'emails_sent_today': EmailEvent.objects.filter(
                    event_type='SENT',
                    created_at__date=timezone.now().date()
                ).count(),
                'campaigns_sending': EmailCampaign.objects.filter(status='SENDING').count(),
                'failed_deliveries_today': EmailEvent.objects.filter(
                    event_type='BOUNCED',
                    created_at__date=timezone.now().date()
                ).count(),
            }
            
            return JsonResponse({'success': True, 'stats': stats})
            
        except Exception as e:
            logger.error(f"Admin quick stats error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class AdminUserActionView(View):
    """Handle admin actions on users"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            action = data.get('action')
            user_ids = data.get('user_ids', [])
            
            if not user_ids:
                return JsonResponse({'success': False, 'error': 'No users selected'})
            
            users = CustomUser.objects.filter(id__in=user_ids)
            
            if action == 'activate':
                users.update(is_active=True)
                message = f'{users.count()} users activated'
                
            elif action == 'deactivate':
                # Don't deactivate super admins
                users = users.exclude(role='SUPER_ADMIN')
                users.update(is_active=False)
                message = f'{users.count()} users deactivated'
                
            elif action == 'verify_email':
                users.update(is_email_verified=True)
                message = f'{users.count()} users email verified'
                
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
            
            # Log admin actions
            for user in users:
                UserActivity.log_activity(
                    user=user,
                    activity_type=f'ADMIN_{action.upper()}',
                    description=f'Bulk {action} by admin {request.user.email}',
                    request=request,
                    metadata={'admin_user': request.user.email}
                )
            
            return JsonResponse({'success': True, 'message': message})
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Admin user action error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class SystemHealthCheckView(View):
    """System health check endpoint"""
    
    def get(self, request):
        try:
            health_data = {
                'database': True,
                'cache': True,
                'email_service': True,
                'disk_space': 'OK',
                'memory_usage': 'OK',
                'timestamp': timezone.now().isoformat(),
            }
            
            # Test database
            try:
                CustomUser.objects.count()
            except Exception:
                health_data['database'] = False
            
            # Test cache
            try:
                cache.set('health_test', 'ok', 10)
                health_data['cache'] = cache.get('health_test') == 'ok'
            except Exception:
                health_data['cache'] = False
            
            # Check recent email failures
            recent_failures = EmailEvent.objects.filter(
                event_type='FAILED',
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            health_data['email_service'] = recent_failures < 100
            health_data['recent_email_failures'] = recent_failures
            
            # Overall health
            health_data['overall_healthy'] = all([
                health_data['database'],
                health_data['cache'],
                health_data['email_service']
            ])
            
            return JsonResponse(health_data)
            
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
            return JsonResponse({
                'overall_healthy': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class ExportUsersView(View):
    """Export user data for admin"""
    
    def get(self, request):
        try:
            format_type = request.GET.get('format', 'csv')
            
            users = CustomUser.objects.all().select_related('profile')
            
            if format_type == 'csv':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="users_export_{timezone.now().strftime("%Y%m%d")}.csv"'
                
                writer = csv.writer(response)
                writer.writerow([
                    'Email', 'Name', 'Company', 'Role', 'Status', 'Verified',
                    'Join Date', 'Last Login', 'Total Campaigns', 'Total Contacts',
                    'Total Emails Sent', 'Country', 'Industry'
                ])
                
                for user in users:
                    profile = getattr(user, 'profile', None)
                    writer.writerow([
                        user.email,
                        user.get_full_name(),
                        user.company,
                        user.get_role_display(),
                        'Active' if user.is_active else 'Inactive',
                        'Yes' if user.is_email_verified else 'No',
                        user.date_joined.date(),
                        user.last_login.date() if user.last_login else '',
                        profile.total_campaigns if profile else 0,
                        profile.total_contacts if profile else 0,
                        profile.total_emails_sent if profile else 0,
                        user.get_country_display(),
                        user.get_industry_display(),
                    ])
                
                return response
            
        except Exception as e:
            logger.error(f"Export users error: {str(e)}")
            messages.error(request, 'Failed to export user data.')
            return redirect('backend:admin_user_list')