

# backend/models/user_models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import validate_email
from django.utils import timezone
import uuid
from datetime import timedelta


class CustomUser(AbstractUser):
    """
    Custom User model for AfriMail Pro with simplified 2-actor system
    """
    
    USER_ROLES = [
        ('SUPER_ADMIN', 'Super Administrator'),
        ('CLIENT', 'Client User'),
    ]
    
    INDUSTRY_CHOICES = [
        ('TECHNOLOGY', 'Technology'),
        ('HEALTHCARE', 'Healthcare'),
        ('EDUCATION', 'Education'),
        ('FINANCE', 'Finance'),
        ('RETAIL', 'Retail'),
        ('MANUFACTURING', 'Manufacturing'),
        ('CONSULTING', 'Consulting'),
        ('MARKETING', 'Marketing & Advertising'),
        ('REAL_ESTATE', 'Real Estate'),
        ('HOSPITALITY', 'Hospitality'),
        ('OTHER', 'Other'),
    ]
    
    COMPANY_SIZE_CHOICES = [
        ('1-5', '1-5 employees'),
        ('6-25', '6-25 employees'),
        ('26-100', '26-100 employees'),
        ('101-500', '101-500 employees'),
        ('500+', '500+ employees'),
    ]
    
    COUNTRY_CHOICES = [
        ('CM', 'Cameroon'),
        ('NG', 'Nigeria'),
        ('KE', 'Kenya'),
        ('GH', 'Ghana'),
        ('ZA', 'South Africa'),
        ('EG', 'Egypt'),
        ('MA', 'Morocco'),
        ('TN', 'Tunisia'),
        ('CI', 'Côte d\'Ivoire'),
        ('SN', 'Senegal'),
        ('OTHER', 'Other'),
    ]
    
    # Core Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, validators=[validate_email])
    
    # Personal Information
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Company Information
    company = models.CharField(max_length=200)
    company_website = models.URLField(blank=True, null=True)
    industry = models.CharField(max_length=20, choices=INDUSTRY_CHOICES, default='OTHER')
    company_size = models.CharField(max_length=10, choices=COMPANY_SIZE_CHOICES, default='1-5')
    
    # Location
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES, default='CM')
    city = models.CharField(max_length=100, blank=True, null=True)
    
    # Role and Permissions
    role = models.CharField(max_length=20, choices=USER_ROLES, default='CLIENT')
    
    # Account Status
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)
    
    # Password Reset
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_sent_at = models.DateTimeField(blank=True, null=True)
    
    # Usage Tracking
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    login_count = models.IntegerField(default=0)
    
    # Preferences
    preferred_language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='Africa/Douala')
    receive_notifications = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Override username field
    username = None
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'company']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        return self.first_name
    
    @property
    def is_super_admin(self):
        return self.role == 'SUPER_ADMIN'
    
    @property
    def is_client(self):
        return self.role == 'CLIENT'
    
    def can_access_admin_panel(self):
        return self.is_super_admin
    
    def get_dashboard_url(self):
        if self.is_super_admin:
            return '/admin-panel/'
        return '/dashboard/'
    
    def generate_email_verification_token(self):
        """Generate and set email verification token"""
        import secrets
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_sent_at = timezone.now()
        self.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
        return self.email_verification_token
    
    def generate_password_reset_token(self):
        """Generate and set password reset token"""
        import secrets
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_sent_at = timezone.now()
        self.save(update_fields=['password_reset_token', 'password_reset_sent_at'])
        return self.password_reset_token
    
    def verify_email(self):
        """Mark email as verified"""
        self.is_email_verified = True
        self.email_verification_token = None
        self.email_verification_sent_at = None
        self.save(update_fields=['is_email_verified', 'email_verification_token', 'email_verification_sent_at'])
    
    def is_password_reset_token_valid(self):
        """Check if password reset token is still valid (24 hours)"""
        if not self.password_reset_token or not self.password_reset_sent_at:
            return False
        return timezone.now() - self.password_reset_sent_at < timedelta(hours=24)


class UserProfile(models.Model):
    """
    Extended user profile for additional settings and preferences
    """
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    
    # Profile Information
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True)
    
    # Marketing Preferences
    email_marketing_consent = models.BooleanField(default=True)
    newsletter_subscription = models.BooleanField(default=True)
    
    # Platform Settings
    dashboard_layout = models.CharField(max_length=20, default='default')
    items_per_page = models.IntegerField(default=20)
    email_signature = models.TextField(blank=True, null=True)
    
    # Usage Statistics
    total_contacts = models.IntegerField(default=0)
    total_campaigns = models.IntegerField(default=0)
    total_emails_sent = models.IntegerField(default=0)
    
    # Account Limits (for Client users)
    max_contacts = models.IntegerField(default=10000)
    max_campaigns_per_month = models.IntegerField(default=100)
    max_emails_per_month = models.IntegerField(default=50000)
    
    # Trial and Billing (for future use)
    is_trial = models.BooleanField(default=True)
    trial_end_date = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Profile"
    
    def update_usage_stats(self):
        """Update usage statistics"""
        self.total_contacts = self.user.contact_set.count()
        self.total_campaigns = self.user.emailcampaign_set.count()
        self.total_emails_sent = self.user.emailcampaign_set.aggregate(
            total=models.Sum('emails_sent')
        )['total'] or 0
        self.save(update_fields=['total_contacts', 'total_campaigns', 'total_emails_sent'])
    
    def can_create_contact(self):
        """Check if user can create more contacts"""
        return self.total_contacts < self.max_contacts
    
    def can_create_campaign(self):
        """Check if user can create more campaigns this month"""
        from django.utils import timezone
        current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        campaigns_this_month = self.user.emailcampaign_set.filter(
            created_at__gte=current_month
        ).count()
        return campaigns_this_month < self.max_campaigns_per_month


class UserActivity(models.Model):
    """
    Track user activities for analytics and security
    """
    
    ACTIVITY_TYPES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('PASSWORD_CHANGE', 'Password Changed'),
        ('EMAIL_VERIFIED', 'Email Verified'),
        ('PROFILE_UPDATED', 'Profile Updated'),
        ('CONTACT_CREATED', 'Contact Created'),
        ('CONTACT_IMPORTED', 'Contacts Imported'),
        ('CAMPAIGN_CREATED', 'Campaign Created'),
        ('CAMPAIGN_SENT', 'Campaign Sent'),
        ('EMAIL_CONFIG_ADDED', 'Email Configuration Added'),
        ('DOMAIN_VERIFIED', 'Domain Verified'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activities')
    
    # Activity Information
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(blank=True, null=True)
    
    # Technical Information
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    # Additional Data
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_activities'
        verbose_name = 'User Activity'
        verbose_name_plural = 'User Activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.activity_type} at {self.created_at}"
    
    @classmethod
    def log_activity(cls, user, activity_type, description=None, request=None, **metadata):
        """Log user activity"""
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = cls.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return cls.objects.create(
            user=user,
            activity_type=activity_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata
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