
# backend/services/analytics_service.py

from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta, date
from ..models import (
    EmailCampaign, EmailEvent, Contact, CustomUser,
    CampaignAnalytics, ContactEngagement, PlatformAnalytics
)
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics and reporting"""
    
    def get_user_dashboard_analytics(self, user, days=30):
        """Get analytics data for user dashboard"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            analytics = {
                'overview': self._get_user_overview(user, start_date, end_date),
                'campaign_performance': self._get_campaign_performance(user, start_date, end_date),
                'engagement_trends': self._get_engagement_trends(user, days),
                'contact_growth': self._get_contact_growth(user, days),
                'top_performing_campaigns': self._get_top_campaigns(user, start_date, end_date),
                'recent_activity': self._get_recent_activity(user, days=7),
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"User dashboard analytics error: {str(e)}")
            return {}
    
    def _get_user_overview(self, user, start_date, end_date):
        """Get user overview statistics"""
        campaigns = user.email_campaigns.filter(
            created_at__range=[start_date, end_date]
        )
        
        events = EmailEvent.objects.filter(
            campaign__user=user,
            created_at__range=[start_date, end_date]
        )
        
        return {
            'total_campaigns': campaigns.count(),
            'emails_sent': events.filter(event_type='SENT').count(),
            'emails_delivered': events.filter(event_type='DELIVERED').count(),
            'emails_opened': events.filter(event_type='OPENED').count(),
            'emails_clicked': events.filter(event_type='CLICKED').count(),
            'unsubscribes': events.filter(event_type='UNSUBSCRIBED').count(),
            'bounces': events.filter(event_type='BOUNCED').count(),
        }
    
    def _get_campaign_performance(self, user, start_date, end_date):
        """Get campaign performance metrics"""
        campaigns = user.email_campaigns.filter(
            status='SENT',
            completed_at__range=[start_date, end_date]
        )
        
        if not campaigns.exists():
            return {
                'avg_open_rate': 0,
                'avg_click_rate': 0,
                'avg_delivery_rate': 0,
                'avg_unsubscribe_rate': 0,
                'total_recipients': 0,
            }
        
        # Calculate averages
        total_delivered = sum([c.emails_delivered for c in campaigns])
        total_sent = sum([c.emails_sent for c in campaigns])
        total_opens = sum([c.unique_opens for c in campaigns])
        total_clicks = sum([c.unique_clicks for c in campaigns])
        total_unsubscribes = sum([c.unsubscribes for c in campaigns])
        
        return {
            'avg_open_rate': (total_opens / total_delivered * 100) if total_delivered > 0 else 0,
            'avg_click_rate': (total_clicks / total_delivered * 100) if total_delivered > 0 else 0,
            'avg_delivery_rate': (total_delivered / total_sent * 100) if total_sent > 0 else 0,
            'avg_unsubscribe_rate': (total_unsubscribes / total_delivered * 100) if total_delivered > 0 else 0,
            'total_recipients': total_delivered,
        }
    
    def _get_engagement_trends(self, user, days):
        """Get engagement trends over time"""
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
        
        return list(reversed(trends))
    
    def _get_contact_growth(self, user, days):
        """Get contact growth over time"""
        growth = []
        
        for i in range(days):
            date_obj = timezone.now().date() - timedelta(days=i)
            
            total_contacts = user.contacts.filter(
                created_at__date__lte=date_obj,
                is_active=True
            ).count()
            
            new_contacts = user.contacts.filter(
                created_at__date=date_obj,
                is_active=True
            ).count()
            
            growth.append({
                'date': date_obj.isoformat(),
                'total_contacts': total_contacts,
                'new_contacts': new_contacts,
            })
        
        return list(reversed(growth))
    
    def _get_top_campaigns(self, user, start_date, end_date, limit=5):
        """Get top performing campaigns"""
        campaigns = user.email_campaigns.filter(
            status='SENT',
            completed_at__range=[start_date, end_date],
            emails_delivered__gt=0
        ).order_by('-unique_opens')[:limit]
        
        top_campaigns = []
        for campaign in campaigns:
            top_campaigns.append({
                'id': str(campaign.id),
                'name': campaign.name,
                'open_rate': campaign.open_rate,
                'click_rate': campaign.click_rate,
                'emails_sent': campaign.emails_sent,
                'unique_opens': campaign.unique_opens,
                'unique_clicks': campaign.unique_clicks,
                'completed_at': campaign.completed_at.isoformat() if campaign.completed_at else None,
            })
        
        return top_campaigns
    
    def _get_recent_activity(self, user, days):
        """Get recent user activity"""
        activities = user.activities.filter(
            created_at__gte=timezone.now() - timedelta(days=days)
        ).order_by('-created_at')[:10]
        
        return [{
            'activity_type': activity.activity_type,
            'description': activity.description,
            'created_at': activity.created_at.isoformat(),
        } for activity in activities]
    
    def get_campaign_detailed_analytics(self, campaign):
        """Get detailed analytics for a specific campaign"""
        try:
            analytics = {
                'basic_stats': {
                    'recipient_count': campaign.recipient_count,
                    'emails_sent': campaign.emails_sent,
                    'emails_delivered': campaign.emails_delivered,
                    'emails_bounced': campaign.emails_bounced,
                    'emails_failed': campaign.emails_failed,
                    'unique_opens': campaign.unique_opens,
                    'total_opens': campaign.total_opens,
                    'unique_clicks': campaign.unique_clicks,
                    'total_clicks': campaign.total_clicks,
                    'unsubscribes': campaign.unsubscribes,
                    'complaints': campaign.complaints,
                },
                'rates': {
                    'delivery_rate': campaign.emails_delivered / campaign.emails_sent * 100 if campaign.emails_sent > 0 else 0,
                    'open_rate': campaign.open_rate,
                    'click_rate': campaign.click_rate,
                    'unsubscribe_rate': campaign.unsubscribe_rate,
                    'bounce_rate': campaign.bounce_rate,
                    'complaint_rate': campaign.complaints / campaign.emails_delivered * 100 if campaign.emails_delivered > 0 else 0,
                },
                'timeline': self._get_campaign_timeline(campaign),
                'geographic_data': self._get_campaign_geographic_data(campaign),
                'device_data': self._get_campaign_device_data(campaign),
                'hourly_activity': self._get_campaign_hourly_activity(campaign),
                'top_links': self._get_campaign_top_links(campaign),
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Campaign detailed analytics error: {str(e)}")
            return {}
    
    def _get_campaign_timeline(self, campaign):
        """Get campaign event timeline by hour"""
        events = EmailEvent.objects.filter(campaign=campaign).order_by('created_at')
        
        timeline = {}
        for event in events:
            hour_key = event.created_at.replace(minute=0, second=0, microsecond=0)
            
            if hour_key not in timeline:
                timeline[hour_key] = {
                    'SENT': 0, 'DELIVERED': 0, 'OPENED': 0, 
                    'CLICKED': 0, 'BOUNCED': 0, 'UNSUBSCRIBED': 0
                }
            
            timeline[hour_key][event.event_type] += 1
        
        # Convert to list format
        timeline_list = []
        for hour, counts in sorted(timeline.items()):
            timeline_list.append({
                'hour': hour.isoformat(),
                **counts
            })
        
        return timeline_list
    
    def _get_campaign_geographic_data(self, campaign):
        """Get geographic distribution of campaign events"""
        geographic_data = EmailEvent.objects.filter(
            campaign=campaign,
            event_type__in=['OPENED', 'CLICKED'],
            country__isnull=False
        ).values('country').annotate(
            opens=Count('id', filter=Q(event_type='OPENED')),
            clicks=Count('id', filter=Q(event_type='CLICKED'))
        ).order_by('-opens')[:10]
        
        return list(geographic_data)
    
    def _get_campaign_device_data(self, campaign):
        """Get device/user agent data for campaign"""
        # This would require parsing user agent strings
        # For now, return placeholder data
        return [
            {'device': 'Desktop', 'count': 150, 'percentage': 60},
            {'device': 'Mobile', 'count': 75, 'percentage': 30},
            {'device': 'Tablet', 'count': 25, 'percentage': 10},
        ]
    
    def _get_campaign_hourly_activity(self, campaign):
        """Get hourly activity pattern for campaign"""
        hourly_data = [0] * 24  # 24 hours
        
        events = EmailEvent.objects.filter(
            campaign=campaign,
            event_type='OPENED'
        )
        
        for event in events:
            hour = event.created_at.hour
            hourly_data[hour] += 1
        
        return [{'hour': i, 'count': count} for i, count in enumerate(hourly_data)]
    
    def _get_campaign_top_links(self, campaign):
        """Get top clicked links in campaign"""
        link_clicks = EmailEvent.objects.filter(
            campaign=campaign,
            event_type='CLICKED',
            clicked_url__isnull=False
        ).values('clicked_url').annotate(
            click_count=Count('id')
        ).order_by('-click_count')[:10]
        
        return list(link_clicks)
    
    def get_platform_analytics(self, days=30):
        """Get platform-wide analytics (for super admins)"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            analytics = {
                'user_stats': self._get_platform_user_stats(start_date, end_date),
                'email_stats': self._get_platform_email_stats(start_date, end_date),
                'performance_metrics': self._get_platform_performance_metrics(start_date, end_date),
                'growth_trends': self._get_platform_growth_trends(days),
                'top_users': self._get_top_users(start_date, end_date),
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Platform analytics error: {str(e)}")
            return {}
    
    def _get_platform_user_stats(self, start_date, end_date):
        """Get platform user statistics"""
        return {
            'total_users': CustomUser.objects.filter(is_active=True).count(),
            'new_users': CustomUser.objects.filter(
                date_joined__range=[start_date, end_date]
            ).count(),
            'active_users': CustomUser.objects.filter(
                last_login__range=[start_date, end_date]
            ).count(),
            'super_admins': CustomUser.objects.filter(
                role='SUPER_ADMIN',
                is_active=True
            ).count(),
            'client_users': CustomUser.objects.filter(
                role='CLIENT',
                is_active=True
            ).count(),
        }
    
    def _get_platform_email_stats(self, start_date, end_date):
        """Get platform email statistics"""
        events = EmailEvent.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        return {
            'total_emails_sent': events.filter(event_type='SENT').count(),
            'total_emails_delivered': events.filter(event_type='DELIVERED').count(),
            'total_emails_opened': events.filter(event_type='OPENED').count(),
            'total_emails_clicked': events.filter(event_type='CLICKED').count(),
            'total_bounces': events.filter(event_type='BOUNCED').count(),
            'total_unsubscribes': events.filter(event_type='UNSUBSCRIBED').count(),
            'total_campaigns': EmailCampaign.objects.filter(
                created_at__range=[start_date, end_date]
            ).count(),
        }
    
    def _get_platform_performance_metrics(self, start_date, end_date):
        """Get platform performance metrics"""
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
            'avg_open_rate': campaigns.aggregate(
                avg=Avg('unique_opens') * 100 / Avg('emails_delivered')
            )['avg'] or 0,
            'avg_click_rate': campaigns.aggregate(
                avg=Avg('unique_clicks') * 100 / Avg('emails_delivered')
            )['avg'] or 0,
            'avg_unsubscribe_rate': campaigns.aggregate(
                avg=Avg('unsubscribes') * 100 / Avg('emails_delivered')
            )['avg'] or 0,
        }
    
    def _get_platform_growth_trends(self, days):
        """Get platform growth trends"""
        trends = []
        
        for i in range(days):
            date_obj = timezone.now().date() - timedelta(days=i)
            
            trends.append({
                'date': date_obj.isoformat(),
                'new_users': CustomUser.objects.filter(
                    date_joined__date=date_obj
                ).count(),
                'new_campaigns': EmailCampaign.objects.filter(
                    created_at__date=date_obj
                ).count(),
                'emails_sent': EmailEvent.objects.filter(
                    event_type='SENT',
                    created_at__date=date_obj
                ).count(),
            })
        
        return list(reversed(trends))
    
    def _get_top_users(self, start_date, end_date, limit=10):
        """Get top users by email volume"""
        top_users = CustomUser.objects.filter(
            is_active=True,
            role='CLIENT'
        ).annotate(
            emails_sent=Count(
                'email_campaigns__events',
                filter=Q(
                    email_campaigns__events__event_type='SENT',
                    email_campaigns__events__created_at__range=[start_date, end_date]
                )
            )
        ).order_by('-emails_sent')[:limit]
        
        return [{
            'user_id': str(user.id),
            'name': user.get_full_name(),
            'email': user.email,
            'company': user.company,
            'emails_sent': user.emails_sent,
        } for user in top_users]