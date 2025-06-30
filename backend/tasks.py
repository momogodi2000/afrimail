

# backend/tasks.py

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from .models import (
    EmailQueue, EmailCampaign, EmailDomainConfig, Contact,
    EmailEvent, CampaignAnalytics, PlatformAnalytics, UserActivity
)
from .services.email_service import EmailService
from .services.analytics_service import AnalyticsService
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_queued_email(self, queue_id):
    """Send a single queued email"""
    try:
        queued_email = EmailQueue.objects.get(id=queue_id)
        
        if queued_email.status != 'PENDING':
            logger.warning(f"Email queue {queue_id} is not pending")
            return
        
        # Mark as sending
        queued_email.status = 'SENDING'
        queued_email.save(update_fields=['status'])
        
        email_service = EmailService()
        campaign = queued_email.campaign
        contact = queued_email.contact
        
        # Send email
        result = email_service.send_email(
            to_email=contact.email,
            subject=queued_email.personalized_subject,
            html_content=queued_email.personalized_html_content,
            text_content=queued_email.personalized_text_content,
            from_email=campaign.from_email,
            from_name=campaign.from_name,
            email_config=campaign.email_config,
            campaign=campaign,
            contact=contact
        )
        
        if result:
            queued_email.mark_sent()
            campaign.increment_sent()
            campaign.increment_delivered()  # Assume delivered for now
            contact.record_email_sent()
            
            logger.info(f"Email sent successfully: {contact.email}")
        else:
            raise Exception("Failed to send email")
    
    except EmailQueue.DoesNotExist:
        logger.error(f"Email queue {queue_id} not found")
        return
    
    except Exception as e:
        logger.error(f"Error sending queued email {queue_id}: {str(e)}")
        
        try:
            queued_email = EmailQueue.objects.get(id=queue_id)
            queued_email.mark_failed(str(e))
            
            # Retry if we haven't exceeded max retries
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying email {queue_id}, attempt {self.request.retries + 1}")
                raise self.retry(countdown=60 * (self.request.retries + 1), exc=e)
            else:
                # Max retries exceeded, mark campaign as having failed emails
                campaign = queued_email.campaign
                campaign.increment_failed()
                
        except EmailQueue.DoesNotExist:
            pass


@shared_task
def process_campaign_queue(campaign_id):
    """Process all queued emails for a campaign"""
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        if campaign.status not in ['SENDING', 'SCHEDULED']:
            logger.warning(f"Campaign {campaign_id} is not in sending status")
            return
        
        # Get pending emails
        pending_emails = EmailQueue.objects.filter(
            campaign=campaign,
            status='PENDING',
            scheduled_at__lte=timezone.now()
        ).order_by('priority', 'scheduled_at')
        
        if not pending_emails.exists():
            # Check if campaign is complete
            if not EmailQueue.objects.filter(
                campaign=campaign,
                status__in=['PENDING', 'RETRYING', 'SENDING']
            ).exists():
                campaign.complete_sending()
            return
        
        # Send emails in batches
        batch_size = 50  # Send 50 emails at a time
        for i in range(0, min(batch_size, pending_emails.count())):
            queued_email = pending_emails[i]
            send_queued_email.delay(str(queued_email.id))
        
        # Schedule next batch if there are more emails
        if pending_emails.count() > batch_size:
            process_campaign_queue.apply_async(
                args=[campaign_id],
                countdown=60  # Wait 1 minute before next batch
            )
        
        logger.info(f"Processed batch for campaign {campaign.name}")
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
    except Exception as e:
        logger.error(f"Error processing campaign queue: {str(e)}")


@shared_task
def send_campaign(campaign_id):
    """Send an email campaign"""
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        if campaign.status != 'SCHEDULED':
            logger.warning(f"Campaign {campaign_id} is not scheduled")
            return
        
        # Start sending
        campaign.start_sending()
        
        # Process the queue
        process_campaign_queue.delay(campaign_id)
        
        logger.info(f"Started sending campaign: {campaign.name}")
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
    except Exception as e:
        logger.error(f"Error starting campaign: {str(e)}")


@shared_task
def schedule_campaigns():
    """Check for campaigns that should be sent now"""
    try:
        current_time = timezone.now()
        
        scheduled_campaigns = EmailCampaign.objects.filter(
            status='SCHEDULED',
            scheduled_at__lte=current_time
        )
        
        for campaign in scheduled_campaigns:
            send_campaign.delay(str(campaign.id))
            logger.info(f"Scheduled campaign for sending: {campaign.name}")
        
    except Exception as e:
        logger.error(f"Error scheduling campaigns: {str(e)}")


@shared_task
def update_engagement_scores():
    """Update engagement scores for all contacts"""
    try:
        contacts = Contact.objects.filter(is_active=True)
        
        updated_count = 0
        for contact in contacts:
            old_score = contact.engagement_score
            new_score = contact.calculate_engagement_score()
            
            if abs(old_score - new_score) > 0.1:  # Only save if significant change
                contact.save(update_fields=['engagement_score'])
                updated_count += 1
        
        logger.info(f"Updated engagement scores for {updated_count} contacts")
        
    except Exception as e:
        logger.error(f"Error updating engagement scores: {str(e)}")


@shared_task
def generate_daily_analytics():
    """Generate daily analytics for all users and platform"""
    try:
        today = timezone.now().date()
        
        # Generate campaign analytics
        campaigns_with_activity = EmailCampaign.objects.filter(
            events__created_at__date=today
        ).distinct()
        
        for campaign in campaigns_with_activity:
            analytics, created = CampaignAnalytics.objects.get_or_create(
                campaign=campaign,
                date=today
            )
            
            # Get events for this campaign today
            events = EmailEvent.objects.filter(
                campaign=campaign,
                created_at__date=today
            )
            
            # Count events by type
            analytics.emails_sent = events.filter(event_type='SENT').count()
            analytics.emails_delivered = events.filter(event_type='DELIVERED').count()
            analytics.unique_opens = events.filter(event_type='OPENED').values('contact').distinct().count()
            analytics.total_opens = events.filter(event_type='OPENED').count()
            analytics.unique_clicks = events.filter(event_type='CLICKED').values('contact').distinct().count()
            analytics.total_clicks = events.filter(event_type='CLICKED').count()
            analytics.emails_bounced = events.filter(event_type='BOUNCED').count()
            analytics.unsubscribes = events.filter(event_type='UNSUBSCRIBED').count()
            
            # Calculate rates
            analytics.calculate_rates()
        
        # Generate platform analytics
        PlatformAnalytics.update_today_stats()
        
        logger.info(f"Generated daily analytics for {today}")
        
    except Exception as e:
        logger.error(f"Error generating daily analytics: {str(e)}")


@shared_task
def cleanup_old_data():
    """Clean up old data to keep database size manageable"""
    try:
        cutoff_date = timezone.now() - timedelta(days=365)  # Keep 1 year of data
        
        # Clean up old email events
        old_events = EmailEvent.objects.filter(created_at__lt=cutoff_date)
        deleted_events = old_events.count()
        old_events.delete()
        
        # Clean up old user activities
        old_activities = UserActivity.objects.filter(created_at__lt=cutoff_date)
        deleted_activities = old_activities.count()
        old_activities.delete()
        
        # Clean up completed email queues
        old_queues = EmailQueue.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['SENT', 'FAILED']
        )
        deleted_queues = old_queues.count()
        old_queues.delete()
        
        logger.info(f"Cleaned up old data: {deleted_events} events, {deleted_activities} activities, {deleted_queues} queues")
        
    except Exception as e:
        logger.error(f"Error cleaning up old data: {str(e)}")


@shared_task
def reset_daily_email_limits():
    """Reset daily email limits for all email configurations"""
    try:
        email_configs = EmailDomainConfig.objects.filter(is_active=True)
        
        updated_count = 0
        for config in email_configs:
            config.reset_daily_usage()
            updated_count += 1
        
        logger.info(f"Reset daily email limits for {updated_count} configurations")
        
    except Exception as e:
        logger.error(f"Error resetting daily email limits: {str(e)}")


@shared_task
def reset_monthly_email_limits():
    """Reset monthly email limits for all email configurations"""
    try:
        email_configs = EmailDomainConfig.objects.filter(is_active=True)
        
        updated_count = 0
        for config in email_configs:
            config.reset_monthly_usage()
            updated_count += 1
        
        logger.info(f"Reset monthly email limits for {updated_count} configurations")
        
    except Exception as e:
        logger.error(f"Error resetting monthly email limits: {str(e)}")


@shared_task
def send_welcome_email(user_id):
    """Send welcome email to new user"""
    try:
        from .models import CustomUser
        user = CustomUser.objects.get(id=user_id)
        
        if not user.is_email_verified:
            logger.warning(f"User {user.email} email not verified, skipping welcome email")
            return
        
        subject = f"Welcome to {settings.PLATFORM_NAME}!"
        
        html_content = f"""
        <h2>Welcome to AfriMail Pro, {user.get_short_name()}!</h2>
        <p>Thank you for joining AfriMail Pro, the premier email marketing platform for Africa.</p>
        
        <h3>Getting Started</h3>
        <ul>
            <li><strong>Complete your profile:</strong> Add your company information and preferences</li>
            <li><strong>Configure your email domain:</strong> Set up your sending domain for better deliverability</li>
            <li><strong>Import your contacts:</strong> Upload your contact lists to start sending campaigns</li>
            <li><strong>Create your first campaign:</strong> Design and send your first email campaign</li>
        </ul>
        
        <h3>Resources</h3>
        <p>Check out our help center for guides and best practices:</p>
        <ul>
            <li>Email domain setup guide</li>
            <li>Contact import tutorial</li>
            <li>Campaign creation walkthrough</li>
            <li>Analytics and reporting overview</li>
        </ul>
        
        <p>If you have any questions, our support team is here to help at support@afrimailpro.com</p>
        
        <p>Best regards,<br>
        The AfriMail Pro Team</p>
        
        <hr>
        <p><small>AfriMail Pro - Connectez l'Afrique, Un Email à la Fois</small></p>
        """
        
        email_service = EmailService()
        result = email_service.send_email(
            to_email=user.email,
            subject=subject,
            html_content=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            from_name=settings.PLATFORM_NAME
        )
        
        if result:
            logger.info(f"Welcome email sent to {user.email}")
        else:
            logger.error(f"Failed to send welcome email to {user.email}")
        
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")


@shared_task
def send_digest_email(user_id, digest_type='weekly'):
    """Send digest email to user"""
    try:
        from .models import CustomUser
        user = CustomUser.objects.get(id=user_id)
        
        if not user.receive_notifications:
            return
        
        analytics_service = AnalyticsService()
        
        if digest_type == 'weekly':
            days = 7
            subject = "Your Weekly AfriMail Pro Summary"
        else:  # monthly
            days = 30
            subject = "Your Monthly AfriMail Pro Report"
        
        # Get user analytics
        analytics = analytics_service.get_user_dashboard_analytics(user, days)
        
        html_content = f"""
        <h2>Your {digest_type.title()} Summary</h2>
        <p>Hi {user.get_short_name()},</p>
        <p>Here's your {digest_type} summary from AfriMail Pro:</p>
        
        <h3>Campaign Performance</h3>
        <ul>
            <li><strong>Campaigns sent:</strong> {analytics.get('overview', {}).get('total_campaigns', 0)}</li>
            <li><strong>Emails delivered:</strong> {analytics.get('overview', {}).get('emails_delivered', 0):,}</li>
            <li><strong>Average open rate:</strong> {analytics.get('campaign_performance', {}).get('avg_open_rate', 0):.1f}%</li>
            <li><strong>Average click rate:</strong> {analytics.get('campaign_performance', {}).get('avg_click_rate', 0):.1f}%</li>
        </ul>
        
        <h3>Contact Growth</h3>
        <p>Your contact list continues to grow! Keep up the great work.</p>
        
        <p>View your full dashboard at <a href="https://afrimailpro.com/dashboard/">AfriMail Pro</a></p>
        
        <p>Best regards,<br>
        The AfriMail Pro Team</p>
        """
        
        email_service = EmailService()
        result = email_service.send_email(
            to_email=user.email,
            subject=subject,
            html_content=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            from_name=settings.PLATFORM_NAME
        )
        
        if result:
            logger.info(f"{digest_type.title()} digest sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Error sending digest email: {str(e)}")

