# backend/models/analytics_models.py

from django.db import models
from django.utils import timezone
from .user_models import CustomUser
from .contact_models import Contact
from .email_models import EmailCampaign
import uuid


class EmailEvent(models.Model):
    """
    Track individual email events (opens, clicks, bounces, etc.)
    """
    
    EVENT_TYPES = [
        ('SENT', 'Email Sent'),
        ('DELIVERED', 'Email Delivered'),
        ('OPENED', 'Email Opened'),
        ('CLICKED', 'Link Clicked'),
        ('BOUNCED', 'Email Bounced'),
        ('UNSUBSCRIBED', 'Unsubscribed'),
        ('COMPLAINED', 'Spam Complaint'),
        ('FAILED', 'Send Failed'),
    ]
    
    BOUNCE_TYPES = [
        ('HARD', 'Hard Bounce'),
        ('SOFT', 'Soft Bounce'),
        ('BLOCK', 'Blocked'),
    ]
    
    # Core Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='events')
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='email_events')
    
    # Event Details
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    event_data = models.JSONField(default=dict, blank=True)
    
    # Technical Information
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    # Location Information (for opens/clicks)
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    
    # Bounce Information
    bounce_type = models.CharField(max_length=10, choices=BOUNCE_TYPES, blank=True, null=True)
    bounce_reason = models.TextField(blank=True, null=True)
    
    # Click Information
    clicked_url = models.URLField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_events'
        verbose_name = 'Email Event'
        verbose_name_plural = 'Email Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', 'event_type']),
            models.Index(fields=['contact', 'event_type']),
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.contact.email} - {self.campaign.name}"
    
    @classmethod
    def log_event(cls, campaign, contact, event_type, **kwargs):
        """Log an email event"""
        return cls.objects.create(
            campaign=campaign,
            contact=contact,
            event_type=event_type,
            event_data=kwargs.get('event_data', {}),
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            country=kwargs.get('country'),
            city=kwargs.get('city'),
            bounce_type=kwargs.get('bounce_type'),
            bounce_reason=kwargs.get('bounce_reason'),
            clicked_url=kwargs.get('clicked_url'),
        )


class CampaignAnalytics(models.Model):
    """
    Daily analytics summary for campaigns
    """
    
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='daily_analytics')
    
    # Date
    date = models.DateField()
    
    # Sending Stats
    emails_sent = models.IntegerField(default=0)
    emails_delivered = models.IntegerField(default=0)
    emails_bounced = models.IntegerField(default=0)
    emails_failed = models.IntegerField(default=0)
    
    # Engagement Stats
    unique_opens = models.IntegerField(default=0)
    total_opens = models.IntegerField(default=0)
    unique_clicks = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    
    # Negative Events
    unsubscribes = models.IntegerField(default=0)
    complaints = models.IntegerField(default=0)
    
    # Calculated Rates
    delivery_rate = models.FloatField(default=0.0)
    open_rate = models.FloatField(default=0.0)
    click_rate = models.FloatField(default=0.0)
    unsubscribe_rate = models.FloatField(default=0.0)
    bounce_rate = models.FloatField(default=0.0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaign_analytics'
        unique_together = ['campaign', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['campaign', 'date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.campaign.name} - {self.date}"
    
    def calculate_rates(self):
        """Calculate all rates"""
        if self.emails_sent > 0:
            self.delivery_rate = (self.emails_delivered / self.emails_sent) * 100
            self.bounce_rate = (self.emails_bounced / self.emails_sent) * 100
        
        if self.emails_delivered > 0:
            self.open_rate = (self.unique_opens / self.emails_delivered) * 100
            self.click_rate = (self.unique_clicks / self.emails_delivered) * 100
            self.unsubscribe_rate = (self.unsubscribes / self.emails_delivered) * 100
        
        self.save(update_fields=[
            'delivery_rate', 'open_rate', 'click_rate', 
            'unsubscribe_rate', 'bounce_rate'
        ])


class ContactEngagement(models.Model):
    """
    Track contact engagement over time
    """
    
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='engagement_history')
    
    # Date
    date = models.DateField()
    
    # Email Activity
    emails_received = models.IntegerField(default=0)
    emails_opened = models.IntegerField(default=0)
    emails_clicked = models.IntegerField(default=0)
    
    # Engagement Score (0-100)
    engagement_score = models.FloatField(default=0.0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contact_engagement'
        unique_together = ['contact', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['contact', 'date']),
            models.Index(fields=['engagement_score']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.contact.email} - {self.date}"
    
    def calculate_engagement_score(self):
        """Calculate engagement score for the day"""
        if self.emails_received == 0:
            self.engagement_score = 0.0
        else:
            open_rate = (self.emails_opened / self.emails_received) * 100
            click_rate = (self.emails_clicked / self.emails_received) * 100
            
            # Weight: Opens 60%, Clicks 40%
            self.engagement_score = (open_rate * 0.6) + (click_rate * 0.4)
        
        self.save(update_fields=['engagement_score'])
        return self.engagement_score


class PlatformAnalytics(models.Model):
    """
    Platform-wide analytics for Super Admin
    """
    
    # Date
    date = models.DateField(unique=True)
    
    # User Stats
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    new_users_today = models.IntegerField(default=0)
    
    # Content Stats
    total_contacts = models.IntegerField(default=0)
    total_campaigns = models.IntegerField(default=0)
    total_templates = models.IntegerField(default=0)
    
    # Email Stats
    emails_sent_today = models.IntegerField(default=0)
    emails_delivered_today = models.IntegerField(default=0)
    emails_opened_today = models.IntegerField(default=0)
    emails_clicked_today = models.IntegerField(default=0)
    
    # Platform Performance
    average_delivery_rate = models.FloatField(default=0.0)
    average_open_rate = models.FloatField(default=0.0)
    average_click_rate = models.FloatField(default=0.0)
    
    # System Health
    api_requests_today = models.IntegerField(default=0)
    failed_requests_today = models.IntegerField(default=0)
    average_response_time = models.FloatField(default=0.0)  # in milliseconds
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'platform_analytics'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"Platform Analytics - {self.date}"
    
    @classmethod
    def update_today_stats(cls):
        """Update today's platform statistics"""
        from django.db.models import Count, Avg
        
        today = timezone.now().date()
        stats, created = cls.objects.get_or_create(date=today)
        
        # User stats
        stats.total_users = CustomUser.objects.filter(is_active=True).count()
        stats.active_users = CustomUser.objects.filter(
            last_login__date=today
        ).count()
        stats.new_users_today = CustomUser.objects.filter(
            date_joined__date=today
        ).count()
        
        # Content stats
        stats.total_contacts = Contact.objects.filter(is_active=True).count()
        stats.total_campaigns = EmailCampaign.objects.count()
        
        # Email stats for today
        today_events = EmailEvent.objects.filter(created_at__date=today)
        stats.emails_sent_today = today_events.filter(event_type='SENT').count()
        stats.emails_delivered_today = today_events.filter(event_type='DELIVERED').count()
        stats.emails_opened_today = today_events.filter(event_type='OPENED').count()
        stats.emails_clicked_today = today_events.filter(event_type='CLICKED').count()
        
        # Calculate average rates
        today_analytics = CampaignAnalytics.objects.filter(date=today)
        if today_analytics.exists():
            stats.average_delivery_rate = today_analytics.aggregate(
                avg=Avg('delivery_rate')
            )['avg'] or 0.0
            stats.average_open_rate = today_analytics.aggregate(
                avg=Avg('open_rate')
            )['avg'] or 0.0
            stats.average_click_rate = today_analytics.aggregate(
                avg=Avg('click_rate')
            )['avg'] or 0.0
        
        stats.save()
        return stats


class ApiUsage(models.Model):
    """
    Track API usage for analytics and rate limiting
    """
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='api_usage')
    
    # Request Information
    endpoint = models.CharField(max_length=200)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    response_time = models.FloatField()  # in milliseconds
    
    # Request Details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'api_usage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['endpoint', 'created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.method} {self.endpoint}"
    
    @classmethod
    def log_request(cls, user, endpoint, method, status_code, response_time, request):
        """Log an API request"""
        ip_address = cls.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return cls.objects.create(
            user=user,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class DomainReputation(models.Model):
    """
    Track domain reputation metrics
    """
    
    domain = models.CharField(max_length=100, unique=True)
    
    # Reputation Metrics
    reputation_score = models.FloatField(default=100.0)  # 0-100 scale
    
    # Volume Stats
    total_emails_sent = models.IntegerField(default=0)
    total_bounces = models.IntegerField(default=0)
    total_complaints = models.IntegerField(default=0)
    
    # Rate Stats
    bounce_rate = models.FloatField(default=0.0)
    complaint_rate = models.FloatField(default=0.0)
    
    # Blacklist Status
    is_blacklisted = models.BooleanField(default=False)
    blacklist_sources = models.JSONField(default=list, blank=True)
    
    # Last Check
    last_checked_at = models.DateTimeField(auto_now=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'domain_reputation'
        ordering = ['-reputation_score']
    
    def __str__(self):
        return f"{self.domain} - {self.reputation_score}%"
    
    def calculate_reputation_score(self):
        """Calculate reputation score based on metrics"""
        if self.total_emails_sent == 0:
            return 100.0
        
        # Calculate rates
        self.bounce_rate = (self.total_bounces / self.total_emails_sent) * 100
        self.complaint_rate = (self.total_complaints / self.total_emails_sent) * 100
        
        # Base score
        score = 100.0
        
        # Deduct for high bounce rate
        if self.bounce_rate > 10:  # > 10% bounce rate
            score -= (self.bounce_rate - 10) * 2
        
        # Deduct for complaints
        if self.complaint_rate > 0.1:  # > 0.1% complaint rate
            score -= (self.complaint_rate - 0.1) * 10
        
        # Deduct if blacklisted
        if self.is_blacklisted:
            score -= 50
        
        # Ensure score is between 0 and 100
        self.reputation_score = max(0, min(100, score))
        self.save(update_fields=['reputation_score', 'bounce_rate', 'complaint_rate'])
        
        return self.reputation_score