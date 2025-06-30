# backend/views/analytics_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView, DetailView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.views import View
import json
import csv
import logging
from datetime import timedelta, date
from collections import defaultdict

from ..models import (
    EmailCampaign, EmailEvent, Contact, ContactList,
    CampaignAnalytics, ContactEngagement, CustomUser
)
from ..services.analytics_service import AnalyticsService
from ..authentication import PermissionManager

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class AnalyticsOverviewView(TemplateView):
    """Main analytics overview dashboard"""
    
    template_name = 'analytics/overview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get date range from request
        days = int(self.request.GET.get('days', 30))
        
        # Get analytics data
        analytics_service = AnalyticsService()
        analytics = analytics_service.get_user_dashboard_analytics(user, days)
        
        context.update({
            'analytics': analytics,
            'days': days,
            'date_range_options': [
                {'value': 7, 'label': 'Last 7 days'},
                {'value': 30, 'label': 'Last 30 days'},
                {'value': 90, 'label': 'Last 3 months'},
                {'value': 365, 'label': 'Last year'},
            ]
        })
        
        # Add quick stats
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        context['quick_stats'] = {
            'total_campaigns': user.email_campaigns.filter(
                created_at__range=[start_date, end_date]
            ).count(),
            'total_emails_sent': EmailEvent.objects.filter(
                campaign__user=user,
                event_type='SENT',
                created_at__range=[start_date, end_date]
            ).count(),
            'avg_open_rate': self._calculate_avg_rate(user, 'OPENED', days),
            'avg_click_rate': self._calculate_avg_rate(user, 'CLICKED', days),
        }
        
        return context
    
    def _calculate_avg_rate(self, user, event_type, days):
        """Calculate average rate for given event type"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        campaigns = user.email_campaigns.filter(
            status='SENT',
            completed_at__range=[start_date, end_date],
            emails_delivered__gt=0
        )
        
        if not campaigns.exists():
            return 0
        
        total_delivered = sum([c.emails_delivered for c in campaigns])
        total_events = EmailEvent.objects.filter(
            campaign__in=campaigns,
            event_type=event_type
        ).values('contact').distinct().count()
        
        return (total_events / total_delivered * 100) if total_delivered > 0 else 0


@method_decorator(login_required, name='dispatch')
class CampaignAnalyticsListView(ListView):
    """List campaign analytics"""
    
    model = EmailCampaign
    template_name = 'analytics/campaign_analytics_list.html'
    context_object_name = 'campaigns'
    paginate_by = 20
    
    def get_queryset(self):
        return EmailCampaign.objects.filter(
            user=self.request.user,
            status='SENT'
        ).order_by('-completed_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add performance summary
        campaigns = self.get_queryset()
        
        if campaigns.exists():
            context['performance_summary'] = {
                'total_campaigns': campaigns.count(),
                'total_emails_sent': sum([c.emails_sent for c in campaigns]),
                'total_emails_delivered': sum([c.emails_delivered for c in campaigns]),
                'avg_open_rate': sum([c.open_rate for c in campaigns]) / campaigns.count(),
                'avg_click_rate': sum([c.click_rate for c in campaigns]) / campaigns.count(),
                'best_performing': campaigns.order_by('-unique_opens').first(),
                'recent_campaign': campaigns.order_by('-completed_at').first(),
            }
        else:
            context['performance_summary'] = None
        
        return context


@method_decorator(login_required, name='dispatch')
class ContactAnalyticsView(TemplateView):
    """Contact analytics and insights"""
    
    template_name = 'analytics/contact_analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get date range
        days = int(self.request.GET.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Contact growth data
        context['contact_growth'] = self._get_contact_growth_data(user, days)
        
        # Engagement distribution
        context['engagement_distribution'] = self._get_engagement_distribution(user)
        
        # Geographic distribution
        context['geographic_distribution'] = self._get_geographic_distribution(user)
        
        # Top engaged contacts
        context['top_contacts'] = Contact.objects.filter(
            user=user,
            is_active=True
        ).order_by('-engagement_score')[:10]
        
        # Contact sources
        context['contact_sources'] = Contact.objects.filter(
            user=user,
            is_active=True,
            source__isnull=False
        ).exclude(source='').values('source').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # List performance
        context['list_performance'] = self._get_list_performance(user)
        
        return context
    
    def _get_contact_growth_data(self, user, days):
        """Get contact growth over time"""
        growth_data = []
        
        for i in range(days):
            date_obj = timezone.now().date() - timedelta(days=i)
            
            total_contacts = Contact.objects.filter(
                user=user,
                created_at__date__lte=date_obj,
                is_active=True
            ).count()
            
            new_contacts = Contact.objects.filter(
                user=user,
                created_at__date=date_obj,
                is_active=True
            ).count()
            
            growth_data.append({
                'date': date_obj.isoformat(),
                'total': total_contacts,
                'new': new_contacts,
            })
        
        return list(reversed(growth_data))
    
    def _get_engagement_distribution(self, user):
        """Get engagement score distribution"""
        contacts = Contact.objects.filter(user=user, is_active=True)
        
        ranges = [
            (0, 20, 'Low'),
            (20, 40, 'Below Average'),
            (40, 60, 'Average'),
            (60, 80, 'Above Average'),
            (80, 100, 'High'),
        ]
        
        distribution = []
        for min_score, max_score, label in ranges:
            count = contacts.filter(
                engagement_score__gte=min_score,
                engagement_score__lt=max_score
            ).count()
            
            distribution.append({
                'label': label,
                'count': count,
                'range': f'{min_score}-{max_score}',
            })
        
        return distribution
    
    def _get_geographic_distribution(self, user):
        """Get geographic distribution of contacts"""
        return Contact.objects.filter(
            user=user,
            is_active=True,
            country__isnull=False
        ).exclude(country='').values('country').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
    
    def _get_list_performance(self, user):
        """Get performance metrics for contact lists"""
        lists_performance = []
        
        for contact_list in ContactList.objects.filter(user=user, is_active=True):
            contacts = contact_list.contacts.filter(is_active=True)
            
            if contacts.exists():
                avg_engagement = contacts.aggregate(
                    avg_score=Avg('engagement_score')
                )['avg_score'] or 0
                
                # Get recent campaign performance for this list
                recent_campaigns = EmailCampaign.objects.filter(
                    user=user,
                    contact_lists=contact_list,
                    status='SENT'
                ).order_by('-completed_at')[:5]
                
                avg_open_rate = 0
                if recent_campaigns.exists():
                    avg_open_rate = sum([c.open_rate for c in recent_campaigns]) / recent_campaigns.count()
                
                lists_performance.append({
                    'list': contact_list,
                    'contact_count': contacts.count(),
                    'avg_engagement_score': round(avg_engagement, 1),
                    'avg_open_rate': round(avg_open_rate, 1),
                    'recent_campaigns': recent_campaigns.count(),
                })
        
        return sorted(lists_performance, key=lambda x: x['avg_engagement_score'], reverse=True)


@method_decorator(login_required, name='dispatch')
class ReportsView(TemplateView):
    """Generate and view reports"""
    
    template_name = 'analytics/reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Available report types
        context['report_types'] = [
            {
                'id': 'campaign_performance',
                'name': 'Campaign Performance Report',
                'description': 'Detailed analysis of your email campaigns',
            },
            {
                'id': 'contact_engagement',
                'name': 'Contact Engagement Report',
                'description': 'Insights into your contact engagement patterns',
            },
            {
                'id': 'list_comparison',
                'name': 'List Comparison Report',
                'description': 'Compare performance across different contact lists',
            },
            {
                'id': 'growth_analysis',
                'name': 'Growth Analysis Report',
                'description': 'Track your list growth and engagement trends',
            },
        ]
        
        # Recent reports (if we stored them)
        context['recent_reports'] = []
        
        return context
    
    def post(self, request):
        """Generate custom report"""
        report_type = request.POST.get('report_type')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        format_type = request.POST.get('format', 'html')
        
        if report_type == 'campaign_performance':
            return self._generate_campaign_performance_report(
                request.user, date_from, date_to, format_type
            )
        elif report_type == 'contact_engagement':
            return self._generate_contact_engagement_report(
                request.user, date_from, date_to, format_type
            )
        # Add other report types as needed
        
        messages.error(request, 'Invalid report type selected.')
        return redirect('backend:reports')
    
    def _generate_campaign_performance_report(self, user, date_from, date_to, format_type):
        """Generate campaign performance report"""
        # Parse dates
        start_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
        
        # Get campaigns in date range
        campaigns = EmailCampaign.objects.filter(
            user=user,
            status='SENT',
            completed_at__date__range=[start_date, end_date]
        ).order_by('-completed_at')
        
        if format_type == 'csv':
            return self._export_campaign_report_csv(campaigns, start_date, end_date)
        else:
            # Render HTML report
            context = {
                'campaigns': campaigns,
                'start_date': start_date,
                'end_date': end_date,
                'summary': self._calculate_campaign_summary(campaigns),
            }
            return render(self.request, 'analytics/reports/campaign_performance.html', context)
    
    def _generate_contact_engagement_report(self, user, date_from, date_to, format_type):
        """Generate contact engagement report"""
        start_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
        
        # Get engagement data
        contacts = Contact.objects.filter(
            user=user,
            is_active=True
        ).order_by('-engagement_score')
        
        if format_type == 'csv':
            return self._export_contact_engagement_csv(contacts, start_date, end_date)
        else:
            context = {
                'contacts': contacts[:100],  # Top 100 contacts
                'start_date': start_date,
                'end_date': end_date,
                'engagement_summary': self._calculate_engagement_summary(contacts),
            }
            return render(self.request, 'analytics/reports/contact_engagement.html', context)
    
    def _export_campaign_report_csv(self, campaigns, start_date, end_date):
        """Export campaign report as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="campaign_report_{start_date}_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Campaign Name', 'Subject', 'Created Date', 'Sent Date',
            'Recipients', 'Emails Sent', 'Delivered', 'Opens', 'Clicks',
            'Unsubscribes', 'Open Rate %', 'Click Rate %', 'Unsubscribe Rate %'
        ])
        
        for campaign in campaigns:
            writer.writerow([
                campaign.name,
                campaign.subject,
                campaign.created_at.date(),
                campaign.completed_at.date() if campaign.completed_at else '',
                campaign.recipient_count,
                campaign.emails_sent,
                campaign.emails_delivered,
                campaign.unique_opens,
                campaign.unique_clicks,
                campaign.unsubscribes,
                round(campaign.open_rate, 2),
                round(campaign.click_rate, 2),
                round(campaign.unsubscribe_rate, 2),
            ])
        
        return response
    
    def _export_contact_engagement_csv(self, contacts, start_date, end_date):
        """Export contact engagement as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="contact_engagement_{start_date}_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Email', 'Name', 'Status', 'Engagement Score',
            'Total Emails Received', 'Total Opens', 'Total Clicks',
            'Open Rate %', 'Click Rate %', 'Last Engagement'
        ])
        
        for contact in contacts:
            writer.writerow([
                contact.email,
                contact.get_full_name(),
                contact.status,
                contact.engagement_score,
                contact.total_emails_received,
                contact.total_emails_opened,
                contact.total_emails_clicked,
                round(contact.open_rate, 2),
                round(contact.click_rate, 2),
                contact.last_email_opened_at or contact.last_email_clicked_at or '',
            ])
        
        return response
    
    def _calculate_campaign_summary(self, campaigns):
        """Calculate summary statistics for campaigns"""
        if not campaigns.exists():
            return {}
        
        return {
            'total_campaigns': campaigns.count(),
            'total_recipients': sum([c.recipient_count for c in campaigns]),
            'total_sent': sum([c.emails_sent for c in campaigns]),
            'total_delivered': sum([c.emails_delivered for c in campaigns]),
            'total_opens': sum([c.unique_opens for c in campaigns]),
            'total_clicks': sum([c.unique_clicks for c in campaigns]),
            'avg_open_rate': sum([c.open_rate for c in campaigns]) / campaigns.count(),
            'avg_click_rate': sum([c.click_rate for c in campaigns]) / campaigns.count(),
        }
    
    def _calculate_engagement_summary(self, contacts):
        """Calculate engagement summary for contacts"""
        if not contacts.exists():
            return {}
        
        return {
            'total_contacts': contacts.count(),
            'avg_engagement_score': contacts.aggregate(avg=Avg('engagement_score'))['avg'] or 0,
            'highly_engaged': contacts.filter(engagement_score__gte=80).count(),
            'moderately_engaged': contacts.filter(
                engagement_score__gte=40,
                engagement_score__lt=80
            ).count(),
            'low_engaged': contacts.filter(engagement_score__lt=40).count(),
        }


@method_decorator(login_required, name='dispatch')
class ExportDataView(View):
    """Export various data types"""
    
    def get(self, request):
        data_type = request.GET.get('type')
        format_type = request.GET.get('format', 'csv')
        
        if data_type == 'campaigns':
            return self._export_campaigns(request.user, format_type)
        elif data_type == 'contacts':
            return self._export_contacts(request.user, format_type)
        elif data_type == 'analytics':
            return self._export_analytics(request.user, format_type)
        else:
            messages.error(request, 'Invalid data type for export.')
            return redirect('backend:analytics_overview')
    
    def _export_campaigns(self, user, format_type):
        """Export campaign data"""
        campaigns = EmailCampaign.objects.filter(user=user).order_by('-created_at')
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="campaigns_export_{timezone.now().strftime("%Y%m%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'Name', 'Subject', 'Status', 'Campaign Type', 'Created',
                'Recipients', 'Sent', 'Delivered', 'Opens', 'Clicks',
                'Open Rate %', 'Click Rate %'
            ])
            
            for campaign in campaigns:
                writer.writerow([
                    campaign.name,
                    campaign.subject,
                    campaign.status,
                    campaign.campaign_type,
                    campaign.created_at.date(),
                    campaign.recipient_count,
                    campaign.emails_sent,
                    campaign.emails_delivered,
                    campaign.unique_opens,
                    campaign.unique_clicks,
                    round(campaign.open_rate, 2),
                    round(campaign.click_rate, 2),
                ])
            
            return response
    
    def _export_contacts(self, user, format_type):
        """Export contact data"""
        # Use existing contact export functionality
        from .contact_views import ContactExportView
        contact_export = ContactExportView()
        contact_export.request = self.request
        return contact_export.get(self.request)
    
    def _export_analytics(self, user, format_type):
        """Export analytics data"""
        # Get analytics data
        analytics_service = AnalyticsService()
        analytics = analytics_service.get_user_dashboard_analytics(user, 30)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="analytics_export_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        # Overview data
        writer.writerow(['Metric', 'Value'])
        overview = analytics.get('overview', {})
        for key, value in overview.items():
            writer.writerow([key.replace('_', ' ').title(), value])
        
        writer.writerow([])  # Empty row
        
        # Performance data
        writer.writerow(['Performance Metrics'])
        performance = analytics.get('campaign_performance', {})
        for key, value in performance.items():
            if isinstance(value, float):
                value = round(value, 2)
            writer.writerow([key.replace('_', ' ').title(), value])
        
        return response


# AJAX Views for Real-time Analytics
@method_decorator(login_required, name='dispatch')
class RealTimeStatsView(View):
    """Get real-time analytics data"""
    
    def get(self, request):
        try:
            user = request.user
            time_range = request.GET.get('range', '24h')
            
            # Calculate time delta
            if time_range == '1h':
                delta = timedelta(hours=1)
            elif time_range == '24h':
                delta = timedelta(hours=24)
            elif time_range == '7d':
                delta = timedelta(days=7)
            else:
                delta = timedelta(days=30)
            
            start_time = timezone.now() - delta
            
            # Get real-time stats
            stats = {
                'emails_sent': EmailEvent.objects.filter(
                    campaign__user=user,
                    event_type='SENT',
                    created_at__gte=start_time
                ).count(),
                'emails_opened': EmailEvent.objects.filter(
                    campaign__user=user,
                    event_type='OPENED',
                    created_at__gte=start_time
                ).count(),
                'emails_clicked': EmailEvent.objects.filter(
                    campaign__user=user,
                    event_type='CLICKED',
                    created_at__gte=start_time
                ).count(),
                'new_contacts': Contact.objects.filter(
                    user=user,
                    created_at__gte=start_time
                ).count(),
                'active_campaigns': EmailCampaign.objects.filter(
                    user=user,
                    status='SENDING'
                ).count(),
            }
            
            return JsonResponse({
                'success': True,
                'stats': stats,
                'last_updated': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Real-time stats error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
class EngagementTrendsView(View):
    """Get engagement trends data"""
    
    def get(self, request):
        try:
            user = request.user
            days = int(request.GET.get('days', 30))
            
            trends = []
            for i in range(days):
                date_obj = timezone.now().date() - timedelta(days=i)
                
                events = EmailEvent.objects.filter(
                    campaign__user=user,
                    created_at__date=date_obj
                )
                
                trends.append({
                    'date': date_obj.isoformat(),
                    'opens': events.filter(event_type='OPENED').count(),
                    'clicks': events.filter(event_type='CLICKED').count(),
                    'unsubscribes': events.filter(event_type='UNSUBSCRIBED').count(),
                })
            
            return JsonResponse({
                'success': True,
                'trends': list(reversed(trends))
            })
            
        except Exception as e:
            logger.error(f"Engagement trends error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
class CampaignComparisonView(View):
    """Compare multiple campaigns"""
    
    def get(self, request):
        try:
            user = request.user
            campaign_ids = request.GET.getlist('campaigns[]')
            
            if not campaign_ids:
                return JsonResponse({'success': False, 'error': 'No campaigns selected'})
            
            campaigns = EmailCampaign.objects.filter(
                id__in=campaign_ids,
                user=user
            )
            
            comparison_data = []
            for campaign in campaigns:
                comparison_data.append({
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'open_rate': campaign.open_rate,
                    'click_rate': campaign.click_rate,
                    'unsubscribe_rate': campaign.unsubscribe_rate,
                    'emails_sent': campaign.emails_sent,
                    'emails_delivered': campaign.emails_delivered,
                    'created_at': campaign.created_at.isoformat(),
                })
            
            return JsonResponse({
                'success': True,
                'campaigns': comparison_data
            })
            
        except Exception as e:
            logger.error(f"Campaign comparison error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})