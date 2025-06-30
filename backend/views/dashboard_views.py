# backend/views/dashboard_views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from ..models import (
    CustomUser, Contact, ContactList, EmailCampaign, EmailDomainConfig,
    EmailEvent, CampaignAnalytics, UserActivity
)
from ..authentication import PermissionManager
from ..services import AnalyticsService
import logging

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    """Main dashboard view - redirects based on user role"""
    
    def get(self, request, *args, **kwargs):
        user = request.user
        
        if user.is_super_admin:
            return redirect('backend:admin_dashboard')
        else:
            return self.render_client_dashboard(request)
    
    def render_client_dashboard(self, request):
        """Render client user dashboard"""
        user = request.user
        
        # Get basic statistics
        total_contacts = user.contacts.filter(is_active=True).count()
        total_campaigns = user.email_campaigns.count()
        total_lists = user.contact_lists.filter(is_active=True).count()
        total_email_configs = user.email_domains.filter(is_active=True).count()
        
        # Get recent campaigns
        recent_campaigns = user.email_campaigns.all()[:5]
        
        # Get campaign statistics for the last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_campaign_stats = user.email_campaigns.filter(
            created_at__gte=thirty_days_ago
        ).aggregate(
            total_sent=Count('id', filter=Q(status='SENT')),
            total_sending=Count('id', filter=Q(status='SENDING')),
            total_draft=Count('id', filter=Q(status='DRAFT'))
        )
        
        # Get top performing campaigns
        top_campaigns = user.email_campaigns.filter(
            status='SENT',
            emails_delivered__gt=0
        ).order_by('-unique_opens')[:3]
        
        # Get contact growth data for the last 7 days
        contact_growth = self.get_contact_growth_data(user)
        
        # Get recent activities
        recent_activities = user.activities.all()[:5]
        
        # Get engagement metrics
        engagement_data = self.get_engagement_metrics(user)
        
        # Check if user has completed setup
        setup_status = self.get_setup_status(user)
        
        context = {
            'user': user,
            'total_contacts': total_contacts,
            'total_campaigns': total_campaigns,
            'total_lists': total_lists,
            'total_email_configs': total_email_configs,
            'recent_campaigns': recent_campaigns,
            'campaign_stats': recent_campaign_stats,
            'top_campaigns': top_campaigns,
            'contact_growth': contact_growth,
            'recent_activities': recent_activities,
            'engagement_data': engagement_data,
            'setup_status': setup_status,
        }
        
        return render(request, 'dashboard/client_dashboard.html', context)
    
    def get_contact_growth_data(self, user):
        """Get contact growth data for charts"""
        growth_data = []
        
        for i in range(7):
            date = timezone.now().date() - timedelta(days=i)
            count = user.contacts.filter(
                created_at__date__lte=date,
                is_active=True
            ).count()
            growth_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        
        return list(reversed(growth_data))
    
    def get_engagement_metrics(self, user):
        """Get user engagement metrics"""
        campaigns = user.email_campaigns.filter(status='SENT')
        
        if not campaigns.exists():
            return {
                'avg_open_rate': 0,
                'avg_click_rate': 0,
                'total_opens': 0,
                'total_clicks': 0,
                'engagement_trend': 'stable'
            }
        
        total_open_rate = sum([c.open_rate for c in campaigns])
        total_click_rate = sum([c.click_rate for c in campaigns])
        
        avg_open_rate = total_open_rate / campaigns.count()
        avg_click_rate = total_click_rate / campaigns.count()
        
        # Get recent trend (last 5 campaigns vs previous 5)
        recent_campaigns = campaigns.order_by('-created_at')[:5]
        previous_campaigns = campaigns.order_by('-created_at')[5:10]
        
        engagement_trend = 'stable'
        if recent_campaigns.exists() and previous_campaigns.exists():
            recent_avg = sum([c.open_rate for c in recent_campaigns]) / recent_campaigns.count()
            previous_avg = sum([c.open_rate for c in previous_campaigns]) / previous_campaigns.count()
            
            if recent_avg > previous_avg + 5:
                engagement_trend = 'up'
            elif recent_avg < previous_avg - 5:
                engagement_trend = 'down'
        
        return {
            'avg_open_rate': round(avg_open_rate, 1),
            'avg_click_rate': round(avg_click_rate, 1),
            'total_opens': sum([c.unique_opens for c in campaigns]),
            'total_clicks': sum([c.unique_clicks for c in campaigns]),
            'engagement_trend': engagement_trend
        }
    
    def get_setup_status(self, user):
        """Check user setup completion status"""
        setup_steps = {
            'profile_completed': bool(
                user.first_name and user.last_name and user.company
            ),
            'email_config_added': user.email_domains.filter(is_active=True).exists(),
            'domain_verified': user.email_domains.filter(
                is_active=True, domain_verified=True
            ).exists(),
            'contacts_added': user.contacts.filter(is_active=True).exists(),
            'first_campaign_sent': user.email_campaigns.filter(status='SENT').exists(),
        }
        
        completed_steps = sum(setup_steps.values())
        total_steps = len(setup_steps)
        completion_percentage = (completed_steps / total_steps) * 100
        
        return {
            'steps': setup_steps,
            'completed': completed_steps,
            'total': total_steps,
            'percentage': completion_percentage,
            'is_complete': completion_percentage == 100
        }


@method_decorator(login_required, name='dispatch')
class QuickStatsAPIView(TemplateView):
    """API view for quick dashboard statistics"""
    
    def get(self, request, *args, **kwargs):
        user = request.user
        
        # Get real-time statistics
        stats = {
            'contacts': {
                'total': user.contacts.filter(is_active=True).count(),
                'active': user.contacts.filter(status='ACTIVE', is_active=True).count(),
                'subscribed_today': user.contacts.filter(
                    subscribed_at__date=timezone.now().date()
                ).count(),
            },
            'campaigns': {
                'total': user.email_campaigns.count(),
                'draft': user.email_campaigns.filter(status='DRAFT').count(),
                'sending': user.email_campaigns.filter(status='SENDING').count(),
                'sent': user.email_campaigns.filter(status='SENT').count(),
            },
            'emails': {
                'sent_today': EmailEvent.objects.filter(
                    campaign__user=user,
                    event_type='SENT',
                    created_at__date=timezone.now().date()
                ).count(),
                'opened_today': EmailEvent.objects.filter(
                    campaign__user=user,
                    event_type='OPENED',
                    created_at__date=timezone.now().date()
                ).count(),
                'clicked_today': EmailEvent.objects.filter(
                    campaign__user=user,
                    event_type='CLICKED',
                    created_at__date=timezone.now().date()
                ).count(),
            }
        }
        
        return JsonResponse(stats)


@method_decorator(login_required, name='dispatch')
class NotificationsView(TemplateView):
    """User notifications view"""
    
    template_name = 'dashboard/notifications.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get notifications (using activities for now)
        notifications = []
        
        # Recent campaign completions
        completed_campaigns = user.email_campaigns.filter(
            status='SENT',
            completed_at__gte=timezone.now() - timedelta(days=7)
        )
        
        for campaign in completed_campaigns:
            notifications.append({
                'type': 'success',
                'title': 'Campaign Completed',
                'message': f'Your campaign "{campaign.name}" has been sent to {campaign.emails_sent} recipients.',
                'timestamp': campaign.completed_at,
                'action_url': f'/campaigns/{campaign.id}/',
            })
        
        # Failed campaigns
        failed_campaigns = user.email_campaigns.filter(
            status='FAILED',
            updated_at__gte=timezone.now() - timedelta(days=7)
        )
        
        for campaign in failed_campaigns:
            notifications.append({
                'type': 'error',
                'title': 'Campaign Failed',
                'message': f'Your campaign "{campaign.name}" failed to send. Please check your email configuration.',
                'timestamp': campaign.updated_at,
                'action_url': f'/campaigns/{campaign.id}/',
            })
        
        # Domain verification reminders
        unverified_domains = user.email_domains.filter(
            domain_verified=False,
            is_active=True
        )
        
        for domain in unverified_domains:
            notifications.append({
                'type': 'warning',
                'title': 'Domain Verification Pending',
                'message': f'Please verify your domain "{domain.domain_name}" to start sending emails.',
                'timestamp': domain.created_at,
                'action_url': f'/email-config/{domain.id}/verify/',
            })
        
        # Sort by timestamp
        notifications.sort(key=lambda x: x['timestamp'], reverse=True)
        
        context.update({
            'notifications': notifications[:20],  # Latest 20 notifications
            'unread_count': len([n for n in notifications if n['timestamp'] > timezone.now() - timedelta(hours=24)]),
        })
        
        return context


@method_decorator(login_required, name='dispatch')
class HelpCenterView(TemplateView):
    """Help center view"""
    
    template_name = 'dashboard/help_center.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Help articles organized by category
        help_articles = {
            'Getting Started': [
                {
                    'title': 'Setting up your first email domain',
                    'description': 'Learn how to configure your email domain for sending campaigns.',
                    'url': '/help/email-domain-setup/',
                },
                {
                    'title': 'Importing your contacts',
                    'description': 'Step-by-step guide to importing contacts from CSV files.',
                    'url': '/help/import-contacts/',
                },
                {
                    'title': 'Creating your first campaign',
                    'description': 'Complete guide to creating and sending your first email campaign.',
                    'url': '/help/first-campaign/',
                },
            ],
            'Email Configuration': [
                {
                    'title': 'SPF, DKIM, and DMARC setup',
                    'description': 'Configure DNS records for better email deliverability.',
                    'url': '/help/dns-setup/',
                },
                {
                    'title': 'Using Gmail/G Suite with AfriMail Pro',
                    'description': 'Connect your Gmail or G Suite account for sending emails.',
                    'url': '/help/gmail-setup/',
                },
            ],
            'Campaigns & Analytics': [
                {
                    'title': 'Understanding email analytics',
                    'description': 'Learn about open rates, click rates, and other important metrics.',
                    'url': '/help/analytics/',
                },
                {
                    'title': 'Best practices for email marketing',
                    'description': 'Tips to improve your email marketing performance.',
                    'url': '/help/best-practices/',
                },
            ],
        }
        
        # FAQ items
        faq_items = [
            {
                'question': 'What is the maximum number of contacts I can have?',
                'answer': 'The default limit is 10,000 contacts. Contact us if you need to increase this limit.',
            },
            {
                'question': 'How many emails can I send per month?',
                'answer': 'The default limit is 50,000 emails per month. This can be adjusted based on your plan.',
            },
            {
                'question': 'Do you support custom SMTP servers?',
                'answer': 'Yes, you can configure custom SMTP servers in addition to using our platform email service.',
            },
            {
                'question': 'How do I improve my email deliverability?',
                'answer': 'Make sure to verify your domain, set up proper DNS records (SPF, DKIM, DMARC), and maintain good sending practices.',
            },
        ]
        
        context.update({
            'help_articles': help_articles,
            'faq_items': faq_items,
        })
        
        return context


@method_decorator(login_required, name='dispatch')
class OnboardingView(TemplateView):
    """User onboarding flow"""
    
    template_name = 'dashboard/onboarding.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Onboarding steps
        steps = [
            {
                'id': 'profile',
                'title': 'Complete Your Profile',
                'description': 'Add your company information and preferences.',
                'completed': bool(user.first_name and user.last_name and user.company),
                'url': '/auth/profile/',
                'icon': 'user'
            },
            {
                'id': 'email_config',
                'title': 'Configure Email Domain',
                'description': 'Set up your email domain for sending campaigns.',
                'completed': user.email_domains.filter(is_active=True).exists(),
                'url': '/email-config/create/',
                'icon': 'mail'
            },
            {
                'id': 'verify_domain',
                'title': 'Verify Your Domain',
                'description': 'Verify your domain ownership for better deliverability.',
                'completed': user.email_domains.filter(domain_verified=True).exists(),
                'url': '/email-config/',
                'icon': 'shield-check'
            },
            {
                'id': 'import_contacts',
                'title': 'Import Contacts',
                'description': 'Upload your contact list to start sending campaigns.',
                'completed': user.contacts.filter(is_active=True).exists(),
                'url': '/contacts/import/',
                'icon': 'users'
            },
            {
                'id': 'first_campaign',
                'title': 'Send Your First Campaign',
                'description': 'Create and send your first email campaign.',
                'completed': user.email_campaigns.filter(status='SENT').exists(),
                'url': '/campaigns/create/',
                'icon': 'send'
            },
        ]
        
        # Calculate progress
        completed_steps = sum(1 for step in steps if step['completed'])
        progress_percentage = (completed_steps / len(steps)) * 100
        
        context.update({
            'steps': steps,
            'completed_steps': completed_steps,
            'total_steps': len(steps),
            'progress_percentage': progress_percentage,
            'is_complete': progress_percentage == 100,
        })
        
        return context


@method_decorator(login_required, name='dispatch')
class SearchView(TemplateView):
    """Global search functionality"""
    
    template_name = 'dashboard/search_results.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()
        
        if not query:
            context.update({
                'query': '',
                'results': {},
                'total_results': 0,
            })
            return context
        
        user = self.request.user
        results = {}
        total_results = 0
        
        # Search contacts
        contacts = user.contacts.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(company__icontains=query),
            is_active=True
        )[:10]
        
        if contacts:
            results['contacts'] = contacts
            total_results += contacts.count()
        
        # Search campaigns
        campaigns = user.email_campaigns.filter(
            Q(name__icontains=query) |
            Q(subject__icontains=query) |
            Q(description__icontains=query)
        )[:10]
        
        if campaigns:
            results['campaigns'] = campaigns
            total_results += campaigns.count()
        
        # Search contact lists
        contact_lists = user.contact_lists.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query),
            is_active=True
        )[:10]
        
        if contact_lists:
            results['contact_lists'] = contact_lists
            total_results += contact_lists.count()
        
        # Search email configurations
        email_configs = user.email_domains.filter(
            Q(domain_name__icontains=query) |
            Q(from_email__icontains=query) |
            Q(from_name__icontains=query),
            is_active=True
        )[:10]
        
        if email_configs:
            results['email_configs'] = email_configs
            total_results += email_configs.count()
        
        context.update({
            'query': query,
            'results': results,
            'total_results': total_results,
        })
        
        return context