# backend/models/contact_models.py

from django.db import models
from django.core.validators import validate_email
from django.utils import timezone
from taggit.managers import TaggableManager
from .user_models import CustomUser
import uuid
import json


class ContactList(models.Model):
    """
    Contact lists/segments for organizing contacts
    """
    
    LIST_TYPES = [
        ('MANUAL', 'Manual List'),
        ('DYNAMIC', 'Dynamic Segment'),
        ('IMPORTED', 'Imported List'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contact_lists')
    
    # List Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    list_type = models.CharField(max_length=20, choices=LIST_TYPES, default='MANUAL')
    
    # Dynamic Segment Conditions (for future use)
    conditions = models.JSONField(default=dict, blank=True)
    
    # Statistics
    contact_count = models.IntegerField(default=0)
    
    # List Settings
    is_active = models.BooleanField(default=True)
    is_favorite = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contact_lists'
        verbose_name = 'Contact List'
        verbose_name_plural = 'Contact Lists'
        unique_together = ['user', 'name']
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['list_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.contact_count} contacts)"
    
    def update_contact_count(self):
        """Update contact count for this list"""
        self.contact_count = self.contacts.filter(is_active=True).count()
        self.save(update_fields=['contact_count'])
    
    def add_contact(self, contact):
        """Add contact to this list"""
        contact.lists.add(self)
        self.update_contact_count()
    
    def remove_contact(self, contact):
        """Remove contact from this list"""
        contact.lists.remove(self)
        self.update_contact_count()


class ContactTag(models.Model):
    """
    Tags for categorizing contacts
    """
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contact_tags')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#3B82F6')  # Hex color code
    description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'contact_tags'
        unique_together = ['user', 'name']
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Contact(models.Model):
    """
    Contact model with comprehensive information and engagement tracking
    """
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('UNSUBSCRIBED', 'Unsubscribed'),
        ('BOUNCED', 'Bounced'),
        ('COMPLAINED', 'Complained'),
        ('BLOCKED', 'Blocked'),
    ]
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('', 'Not Specified'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contacts')
    
    # Core Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(validators=[validate_email])
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    
    # Personal Details
    phone = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # Address Information
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Professional Information
    company = models.CharField(max_length=200, blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    
    # Contact Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    is_active = models.BooleanField(default=True)
    
    # Subscription Management
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)
    unsubscribe_reason = models.TextField(blank=True, null=True)
    
    # Lists and Tags
    lists = models.ManyToManyField(ContactList, related_name='contacts', blank=True)
    tags = models.ManyToManyField(ContactTag, related_name='contacts', blank=True)
    
    # Engagement Metrics
    total_emails_received = models.IntegerField(default=0)
    total_emails_opened = models.IntegerField(default=0)
    total_emails_clicked = models.IntegerField(default=0)
    last_email_opened_at = models.DateTimeField(blank=True, null=True)
    last_email_clicked_at = models.DateTimeField(blank=True, null=True)
    engagement_score = models.FloatField(default=0.0)
    
    # Source Tracking
    source = models.CharField(max_length=100, blank=True, null=True)
    referrer = models.CharField(max_length=200, blank=True, null=True)
    utm_source = models.CharField(max_length=100, blank=True, null=True)
    utm_medium = models.CharField(max_length=100, blank=True, null=True)
    utm_campaign = models.CharField(max_length=100, blank=True, null=True)
    
    # Custom Fields (JSON for flexibility)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contacts'
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'
        unique_together = ['user', 'email']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'email']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['engagement_score']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.email.split('@')[0].title()
    
    def get_short_name(self):
        return self.first_name or self.email.split('@')[0].title()
    
    @property
    def open_rate(self):
        """Calculate email open rate"""
        if self.total_emails_received == 0:
            return 0
        return (self.total_emails_opened / self.total_emails_received) * 100
    
    @property
    def click_rate(self):
        """Calculate email click rate"""
        if self.total_emails_received == 0:
            return 0
        return (self.total_emails_clicked / self.total_emails_received) * 100
    
    def calculate_engagement_score(self):
        """Calculate engagement score based on email interactions"""
        if self.total_emails_received == 0:
            return 0
        
        # Base score on open and click rates
        open_score = self.open_rate * 0.6  # 60% weight for opens
        click_score = self.click_rate * 0.4  # 40% weight for clicks
        
        # Bonus for recent activity
        recent_bonus = 0
        if self.last_email_opened_at:
            days_since_open = (timezone.now() - self.last_email_opened_at).days
            if days_since_open <= 7:
                recent_bonus += 10
            elif days_since_open <= 30:
                recent_bonus += 5
        
        score = min(100, open_score + click_score + recent_bonus)
        self.engagement_score = round(score, 2)
        return self.engagement_score
    
    def unsubscribe(self, reason=None):
        """Unsubscribe contact"""
        self.status = 'UNSUBSCRIBED'
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.unsubscribe_reason = reason
        self.save(update_fields=[
            'status', 'is_active', 'unsubscribed_at', 'unsubscribe_reason'
        ])
    
    def resubscribe(self):
        """Resubscribe contact"""
        self.status = 'ACTIVE'
        self.is_active = True
        self.unsubscribed_at = None
        self.unsubscribe_reason = None
        self.save(update_fields=[
            'status', 'is_active', 'unsubscribed_at', 'unsubscribe_reason'
        ])
    
    def add_to_list(self, contact_list):
        """Add contact to a specific list"""
        self.lists.add(contact_list)
        contact_list.update_contact_count()
    
    def remove_from_list(self, contact_list):
        """Remove contact from a specific list"""
        self.lists.remove(contact_list)
        contact_list.update_contact_count()
    
    def get_custom_field(self, field_name, default=None):
        """Get custom field value"""
        return self.custom_fields.get(field_name, default)
    
    def set_custom_field(self, field_name, value):
        """Set custom field value"""
        self.custom_fields[field_name] = value
        self.save(update_fields=['custom_fields'])
    
    def record_email_sent(self):
        """Record that an email was sent to this contact"""
        self.total_emails_received += 1
        self.save(update_fields=['total_emails_received'])
    
    def record_email_opened(self):
        """Record that this contact opened an email"""
        self.total_emails_opened += 1
        self.last_email_opened_at = timezone.now()
        self.calculate_engagement_score()
        self.save(update_fields=[
            'total_emails_opened', 'last_email_opened_at', 'engagement_score'
        ])
    
    def record_email_clicked(self):
        """Record that this contact clicked a link in an email"""
        self.total_emails_clicked += 1
        self.last_email_clicked_at = timezone.now()
        self.calculate_engagement_score()
        self.save(update_fields=[
            'total_emails_clicked', 'last_email_clicked_at', 'engagement_score'
        ])


class ContactImport(models.Model):
    """
    Track contact import operations
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contact_imports')
    
    # Import Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Import Results
    total_rows = models.IntegerField(default=0)
    successful_imports = models.IntegerField(default=0)
    failed_imports = models.IntegerField(default=0)
    duplicates_found = models.IntegerField(default=0)
    
    # Error Tracking
    errors = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    # List Assignment
    target_list = models.ForeignKey(
        ContactList, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='imports'
    )
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'contact_imports'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Import {self.file_name} - {self.status}"
    
    def mark_completed(self):
        """Mark import as completed"""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def mark_failed(self, error_message):
        """Mark import as failed"""
        self.status = 'FAILED'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])
    
    def add_error(self, row_number, error_message):
        """Add an import error"""
        self.errors.append({
            'row': row_number,
            'error': error_message,
            'timestamp': timezone.now().isoformat()
        })
        self.save(update_fields=['errors'])
    
    @property
    def success_rate(self):
        """Calculate import success rate"""
        if self.total_rows == 0:
            return 0
        return (self.successful_imports / self.total_rows) * 100