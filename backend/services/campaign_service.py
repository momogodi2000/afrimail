# backend/services/campaign_service.py

from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Avg
from ..models import EmailCampaign, Contact, EmailEvent, EmailQueue, CampaignAnalytics
from .email_service import EmailService
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class CampaignService:
    """Service for managing email campaigns"""
    
    def __init__(self):
        self.email_service = EmailService()
    
    def create_campaign(self, user, campaign_data):
        """Create a new campaign"""
        try:
            with transaction.atomic():
                campaign = EmailCampaign.objects.create(
                    user=user,
                    **campaign_data
                )
                
                # Calculate recipient count
                campaign.calculate_recipient_count()
                
                logger.info(f"Campaign created: {campaign.name} by {user.email}")
                return {'success': True, 'campaign': campaign}
                
        except Exception as e:
            logger.error(f"Campaign creation error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def duplicate_campaign(self, campaign, new_name=None):
        """Duplicate an existing campaign"""
        try:
            duplicate = campaign.duplicate(new_name)
            logger.info(f"Campaign duplicated: {duplicate.name}")
            return {'success': True, 'campaign': duplicate}
        except Exception as e:
            logger.error(f"Campaign duplication error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_campaign(self, campaign):
        """Send a campaign"""
        try:
            # Validate campaign before sending
            validation_result = self.validate_campaign_for_sending(campaign)
            if not validation_result['valid']:
                return {'success': False, 'error': validation_result['error']}
            
            # Start sending process
            result = self.email_service.send_bulk_campaign(campaign)
            
            if result:
                logger.info(f"Campaign sending started: {campaign.name}")
                return {'success': True, 'message': 'Campaign sending started successfully'}
            else:
                return {'success': False, 'error': 'Failed to start campaign sending'}
                
        except Exception as e:
            logger.error(f"Campaign sending error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def validate_campaign_for_sending(self, campaign):
        """Validate campaign before sending"""
        try:
            # Check if campaign is in draft status
            if campaign.status != 'DRAFT':
                return {'valid': False, 'error': 'Campaign is not in draft status'}
            
            # Check if email configuration exists and is verified
            if not campaign.email_config:
                return {'valid': False, 'error': 'No email configuration selected'}
            
            if not campaign.email_config.domain_verified:
                return {'valid': False, 'error': 'Email domain is not verified'}
            
            # Check if campaign has recipients
            if campaign.recipient_count == 0:
                return {'valid': False, 'error': 'Campaign has no recipients'}
            
            # Check if email configuration can send emails
            if not campaign.email_config.can_send_email():
                return {'valid': False, 'error': 'Email configuration has reached sending limits'}
            
            # Check if content exists
            if not campaign.html_content and not campaign.text_content:
                return {'valid': False, 'error': 'Campaign has no content'}
            
            # Check if subject exists
            if not campaign.subject:
                return {'valid': False, 'error': 'Campaign has no subject'}
            
            return {'valid': True}
            
        except Exception as e:
            logger.error(f"Campaign validation error: {str(e)}")
            return {'valid': False, 'error': str(e)}
    
    def pause_campaign(self, campaign):
        """Pause a running campaign"""
        try:
            if campaign.status == 'SENDING':
                campaign.pause_sending()
                logger.info(f"Campaign paused: {campaign.name}")
                return {'success': True, 'message': 'Campaign paused successfully'}
            else:
                return {'success': False, 'error': 'Campaign is not currently sending'}
        except Exception as e:
            logger.error(f"Campaign pause error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def resume_campaign(self, campaign):
        """Resume a paused campaign"""
        try:
            if campaign.status == 'PAUSED':
                campaign.status = 'SENDING'
                campaign.save(update_fields=['status'])
                
                # Resume processing queue
                self.email_service.send_bulk_campaign(campaign)
                
                logger.info(f"Campaign resumed: {campaign.name}")
                return {'success': True, 'message': 'Campaign resumed successfully'}
            else:
                return {'success': False, 'error': 'Campaign is not paused'}
        except Exception as e:
            logger.error(f"Campaign resume error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def cancel_campaign(self, campaign):
        """Cancel a campaign"""
        try:
            if campaign.status in ['SENDING', 'PAUSED', 'SCHEDULED']:
                campaign.cancel_sending()
                
                # Cancel pending emails in queue
                EmailQueue.objects.filter(
                    campaign=campaign,
                    status='PENDING'
                ).update(status='CANCELLED')
                
                logger.info(f"Campaign cancelled: {campaign.name}")
                return {'success': True, 'message': 'Campaign cancelled successfully'}
            else:
                return {'success': False, 'error': 'Campaign cannot be cancelled in current status'}
        except Exception as e:
            logger.error(f"Campaign cancel error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_campaign_statistics(self, campaign):
        """Get detailed campaign statistics"""
        try:
            stats = {
                'basic': {
                    'recipient_count': campaign.recipient_count,
                    'emails_sent': campaign.emails_sent,
                    'emails_delivered': campaign.emails_delivered,
                    'emails_bounced': campaign.emails_bounced,
                    'emails_failed': campaign.emails_failed,
                },
                'engagement': {
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
                },
                'timing': {
                    'created_at': campaign.created_at,
                    'started_at': campaign.started_at,
                    'completed_at': campaign.completed_at,
                    'duration': None,
                }
            }
            
            # Calculate duration if campaign is completed
            if campaign.started_at and campaign.completed_at:
                duration = campaign.completed_at - campaign.started_at
                stats['timing']['duration'] = duration.total_seconds()
            
            return stats
            
        except Exception as e:
            logger.error(f"Campaign statistics error: {str(e)}")
            return {}
    
    def get_campaign_timeline(self, campaign):
        """Get campaign event timeline"""
        try:
            timeline = []
            
            # Campaign events
            timeline.append({
                'time': campaign.created_at,
                'event': 'Campaign Created',
                'description': f'Campaign "{campaign.name}" was created',
                'type': 'info'
            })
            
            if campaign.started_at:
                timeline.append({
                    'time': campaign.started_at,
                    'event': 'Sending Started',
                    'description': 'Campaign sending began',
                    'type': 'success'
                })
            
            if campaign.completed_at:
                timeline.append({
                    'time': campaign.completed_at,
                    'event': 'Sending Completed',
                    'description': f'Campaign sent to {campaign.emails_sent} recipients',
                    'type': 'success'
                })
            
            # Add major email events
            events = EmailEvent.objects.filter(campaign=campaign).order_by('created_at')
            
            # Group events by hour for summary
            hourly_events = {}
            for event in events:
                hour_key = event.created_at.replace(minute=0, second=0, microsecond=0)
                if hour_key not in hourly_events:
                    hourly_events[hour_key] = {}
                
                event_type = event.event_type
                if event_type not in hourly_events[hour_key]:
                    hourly_events[hour_key][event_type] = 0
                hourly_events[hour_key][event_type] += 1
            
            # Add hourly summaries to timeline
            for hour, events_summary in hourly_events.items():
                description_parts = []
                for event_type, count in events_summary.items():
                    description_parts.append(f"{count} {event_type.lower()}")
                
                timeline.append({
                    'time': hour,
                    'event': 'Email Activity',
                    'description': ', '.join(description_parts),
                    'type': 'info'
                })
            
            # Sort timeline by time
            timeline.sort(key=lambda x: x['time'])
            
            return timeline
            
        except Exception as e:
            logger.error(f"Campaign timeline error: {str(e)}")
            return []
    
    def get_user_campaign_summary(self, user, days=30):
        """Get campaign summary for user"""
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            campaigns = user.email_campaigns.filter(created_at__gte=start_date)
            
            summary = {
                'total_campaigns': campaigns.count(),
                'sent_campaigns': campaigns.filter(status='SENT').count(),
                'sending_campaigns': campaigns.filter(status='SENDING').count(),
                'draft_campaigns': campaigns.filter(status='DRAFT').count(),
                'failed_campaigns': campaigns.filter(status='FAILED').count(),
                'total_emails_sent': sum([c.emails_sent for c in campaigns]),
                'total_opens': sum([c.unique_opens for c in campaigns]),
                'total_clicks': sum([c.unique_clicks for c in campaigns]),
                'avg_open_rate': 0,
                'avg_click_rate': 0,
            }
            
            # Calculate average rates
            sent_campaigns = campaigns.filter(status='SENT', emails_delivered__gt=0)
            if sent_campaigns.exists():
                summary['avg_open_rate'] = sent_campaigns.aggregate(
                    avg_open_rate=Avg('unique_opens') * 100 / Avg('emails_delivered')
                )['avg_open_rate'] or 0
                
                summary['avg_click_rate'] = sent_campaigns.aggregate(
                    avg_click_rate=Avg('unique_clicks') * 100 / Avg('emails_delivered')
                )['avg_click_rate'] or 0
            
            return summary
            
        except Exception as e:
            logger.error(f"User campaign summary error: {str(e)}")
            return {}

