# backend/models/email_models.py

from django.db import models
from django.core.validators import validate_email
from django.utils import timezone
from .user_models import CustomUser
from .contact_models import ContactList
import uuid
import json


class EmailDomainConfig(models.Model):
    """
    Email domain configuration for users to set up their own SMTP settings
    """
    
    SMTP_PROVIDERS = [
        ('GMAIL', 'Gmail (G Suite)'),
        ('OUTLOOK', 'Outlook 365'),
        ('SENDGRID', 'SendGrid'),
        ('MAILGUN', 'Mailgun'),
        ('AMAZON_SES', 'Amazon SES'),
        ('YAGMAIL', 'Yagmail (Gmail)'),
        ('CUSTOM', 'Custom SMTP'),
        ('PLATFORM', 'AfriMail Pro Platform'),
    ]
    
    VERIFICATION_STATUS = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('FAILED', 'Verification Failed'),
        ('EXPIRED', 'Verification Expired'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_domains')
    
    # Domain Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain_name = models.CharField(max_length=100, help_text="e.g., mycompany.com")
    from_email = models.EmailField(help_text="e.g., marketing@mycompany.com")
    from_name = models.CharField(max_length=100, help_text="e.g., MyCompany Marketing")
    reply_to_email = models.EmailField(blank=True, null=True)
    
    # SMTP Configuration
    smtp_provider = models.CharField(max_length=20, choices=SMTP_PROVIDERS, default='PLATFORM')
    smtp_host = models.CharField(max_length=100, blank=True, null=True)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=100, blank=True, null=True)
    smtp_password = models.CharField(max_length=500, blank=True, null=True)  # Encrypted
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    
    # Domain Verification
    domain_verified = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='PENDING')
    verification_token = models.CharField(max_length=100, blank=True, null=True)
    verification_attempts = models.IntegerField(default=0)
    last_verification_attempt = models.DateTimeField(blank=True, null=True)
    
    # DNS Records for verification
    spf_record = models.TextField(blank=True, null=True)
    dkim_record = models.TextField(blank=True, null=True)
    dmarc_record = models.TextField(blank=True, null=True)
    
    # Usage Settings
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    daily_send_limit = models.IntegerField(default=1000)
    monthly_send_limit = models.IntegerField(default=10000)
    
    # Usage Tracking
    emails_sent_today = models.IntegerField(default=0)
    emails_sent_this_month = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_domain_configs'
        verbose_name = 'Email Domain Configuration'
        verbose_name_plural = 'Email Domain Configurations'
        unique_together = ['user', 'domain_name']
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['domain_verified']),
            models.Index(fields=['smtp_provider']),
        ]
    
    def __str__(self):
        return f"{self.domain_name} ({self.from_email})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default config per user
        if self.is_default:
            EmailDomainConfig.objects.filter(
                user=self.user, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    def can_send_email(self):
        """Check if domain can send emails based on limits"""
        if not self.is_active or not self.domain_verified:
            return False
        
        if self.emails_sent_today >= self.daily_send_limit:
            return False
        
        if self.emails_sent_this_month >= self.monthly_send_limit:
            return False
        
        return True
    
    def increment_usage(self):
        """Increment usage counters"""
        self.emails_sent_today += 1
        self.emails_sent_this_month += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['emails_sent_today', 'emails_sent_this_month', 'last_used_at'])
    
    def reset_daily_usage(self):
        """Reset daily usage counter"""
        self.emails_sent_today = 0
        self.save(update_fields=['emails_sent_today'])
    
    def reset_monthly_usage(self):
        """Reset monthly usage counter"""
        self.emails_sent_this_month = 0
        self.save(update_fields=['emails_sent_this_month'])
    
    def generate_verification_token(self):
        """Generate verification token"""
        import secrets
        self.verification_token = secrets.token_urlsafe(32)
        self.save(update_fields=['verification_token'])
        return self.verification_token
    
    def verify_domain(self):
        """Mark domain as verified"""
        self.domain_verified = True
        self.verification_status = 'VERIFIED'
        self.save(update_fields=['domain_verified', 'verification_status'])


class EmailTemplate(models.Model):
    """
    Email templates for campaigns
    """
    
    TEMPLATE_TYPES = [
        ('NEWSLETTER', 'Newsletter'),
        ('PROMOTIONAL', 'Promotional'),
        ('TRANSACTIONAL', 'Transactional'),
        ('WELCOME', 'Welcome Series'),
        ('ANNOUNCEMENT', 'Announcement'),
        ('CUSTOM', 'Custom'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_templates')
    
    # Template Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, default='CUSTOM')
    
    # Email Content
    subject = models.CharField(max_length=255)
    html_content = models.TextField()
    text_content = models.TextField(blank=True, null=True)
    
    # Template Settings
    is_active = models.BooleanField(default=True)
    is_shared = models.BooleanField(default=False)  # For sharing templates
    
    # Usage Tracking
    usage_count = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_templates'
        verbose_name = 'Email Template'
        verbose_name_plural = 'Email Templates'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['template_type']),
            models.Index(fields=['usage_count']),
        ]
    
    def __str__(self):
        return self.name
    
    def increment_usage(self):
        """Increment usage counter"""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])


class EmailCampaign(models.Model):
    """
    Email campaigns for sending bulk emails
    """
    
    CAMPAIGN_TYPES = [
        ('REGULAR', 'Regular Campaign'),
        ('A_B_TEST', 'A/B Test Campaign'),
        ('AUTORESPONDER', 'Autoresponder'),
        ('RSS', 'RSS Campaign'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('PAUSED', 'Paused'),
        ('CANCELLED', 'Cancelled'),
        ('FAILED', 'Failed'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_campaigns')
    
    # Campaign Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES, default='REGULAR')
    
    # Email Configuration
    email_config = models.ForeignKey(
        EmailDomainConfig, 
        on_delete=models.CASCADE, 
        related_name='campaigns',
        blank=True, 
        null=True
    )
    template = models.ForeignKey(
        EmailTemplate, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='campaigns'
    )
    
    # Email Content
    subject = models.CharField(max_length=255)
    from_name = models.CharField(max_length=100)
    from_email = models.EmailField()
    reply_to_email = models.EmailField(blank=True, null=True)
    html_content = models.TextField()
    text_content = models.TextField(blank=True, null=True)
    
    # Recipients
    contact_lists = models.ManyToManyField(ContactList, related_name='campaigns', blank=True)
    recipient_count = models.IntegerField(default=0)
    
    # Scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    scheduled_at = models.DateTimeField(blank=True, null=True)
    send_immediately = models.BooleanField(default=False)
    
    # Campaign Settings
    track_opens = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)
    track_unsubscribes = models.BooleanField(default=True)
    
    # Sending Progress
    emails_sent = models.IntegerField(default=0)
    emails_delivered = models.IntegerField(default=0)
    emails_bounced = models.IntegerField(default=0)
    emails_failed = models.IntegerField(default=0)
    
    # Analytics
    unique_opens = models.IntegerField(default=0)
    total_opens = models.IntegerField(default=0)
    unique_clicks = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    unsubscribes = models.IntegerField(default=0)
    complaints = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'email_campaigns'
        verbose_name = 'Email Campaign'
        verbose_name_plural = 'Email Campaigns'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.status}"
    
    @property
    def open_rate(self):
        """Calculate open rate"""
        if self.emails_delivered == 0:
            return 0
        return (self.unique_opens / self.emails_delivered) * 100
    
    @property
    def click_rate(self):
        """Calculate click rate"""
        if self.emails_delivered == 0:
            return 0
        return (self.unique_clicks / self.emails_delivered) * 100
    
    @property
    def unsubscribe_rate(self):
        """Calculate unsubscribe rate"""
        if self.emails_delivered == 0:
            return 0
        return (self.unsubscribes / self.emails_delivered) * 100
    
    @property
    def bounce_rate(self):
        """Calculate bounce rate"""
        if self.emails_sent == 0:
            return 0
        return (self.emails_bounced / self.emails_sent) * 100
    
    def calculate_recipient_count(self):
        """Calculate total recipient count from all lists"""
        total = 0
        for contact_list in self.contact_lists.all():
            total += contact_list.contacts.filter(is_active=True, status='ACTIVE').count()
        self.recipient_count = total
        self.save(update_fields=['recipient_count'])
        return total
    
    def start_sending(self):
        """Mark campaign as started"""
        self.status = 'SENDING'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def complete_sending(self):
        """Mark campaign as completed"""
        self.status = 'SENT'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def pause_sending(self):
        """Pause campaign"""
        self.status = 'PAUSED'
        self.save(update_fields=['status'])
    
    def cancel_sending(self):
        """Cancel campaign"""
        self.status = 'CANCELLED'
        self.save(update_fields=['status'])
    
    def increment_sent(self):
        """Increment sent counter"""
        self.emails_sent += 1
        self.save(update_fields=['emails_sent'])
    
    def increment_delivered(self):
        """Increment delivered counter"""
        self.emails_delivered += 1
        self.save(update_fields=['emails_delivered'])
    
    def increment_bounced(self):
        """Increment bounced counter"""
        self.emails_bounced += 1
        self.save(update_fields=['emails_bounced'])
    
    def increment_failed(self):
        """Increment failed counter"""
        self.emails_failed += 1
        self.save(update_fields=['emails_failed'])
    
    def record_open(self, is_unique=True):
        """Record email open"""
        self.total_opens += 1
        if is_unique:
            self.unique_opens += 1
        self.save(update_fields=['total_opens', 'unique_opens'])
    
    def record_click(self, is_unique=True):
        """Record email click"""
        self.total_clicks += 1
        if is_unique:
            self.unique_clicks += 1
        self.save(update_fields=['total_clicks', 'unique_clicks'])
    
    def record_unsubscribe(self):
        """Record unsubscribe"""
        self.unsubscribes += 1
        self.save(update_fields=['unsubscribes'])
    
    def record_complaint(self):
        """Record spam complaint"""
        self.complaints += 1
        self.save(update_fields=['complaints'])
    
    def duplicate(self, new_name=None):
        """Create a duplicate of this campaign"""
        if not new_name:
            new_name = f"Copy of {self.name}"
        
        duplicate = EmailCampaign.objects.create(
            user=self.user,
            name=new_name,
            description=self.description,
            campaign_type=self.campaign_type,
            email_config=self.email_config,
            template=self.template,
            subject=self.subject,
            from_name=self.from_name,
            from_email=self.from_email,
            reply_to_email=self.reply_to_email,
            html_content=self.html_content,
            text_content=self.text_content,
            track_opens=self.track_opens,
            track_clicks=self.track_clicks,
            track_unsubscribes=self.track_unsubscribes,
            priority=self.priority,
        )
        
        # Copy contact lists
        duplicate.contact_lists.set(self.contact_lists.all())
        duplicate.calculate_recipient_count()
        
        return duplicate


class EmailQueue(models.Model):
    """
    Queue for managing email sending
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('RETRYING', 'Retrying'),
    ]
    
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='email_queue')
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE, related_name='queued_emails')
    
    # Queue Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    priority = models.IntegerField(default=0)  # Lower number = higher priority
    
    # Personalized Content
    personalized_subject = models.CharField(max_length=255)
    personalized_html_content = models.TextField()
    personalized_text_content = models.TextField(blank=True, null=True)
    
    # Sending Information
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    error_message = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'email_queue'
        ordering = ['priority', 'scheduled_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return f"Email to {self.contact.email} - {self.status}"
    
    def mark_sent(self):
        """Mark email as sent"""
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_failed(self, error_message):
        """Mark email as failed"""
        self.attempts += 1
        self.error_message = error_message
        
        if self.attempts >= self.max_attempts:
            self.status = 'FAILED'
        else:
            self.status = 'RETRYING'
            # Schedule retry for later
            self.scheduled_at = timezone.now() + timezone.timedelta(minutes=5 * self.attempts)
        
        self.save(update_fields=['status', 'attempts', 'error_message', 'scheduled_at'])