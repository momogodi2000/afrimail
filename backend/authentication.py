# backend/authentication.py

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from .models import CustomUser, UserProfile, UserActivity
from .services.email_service import EmailService
import secrets
import hashlib
import re
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Comprehensive authentication service for AfriMail Pro"""
    
    def __init__(self):
        self.email_service = EmailService()
    
    def register_user(self, user_data, request=None):
        """Register new user with comprehensive validation"""
        try:
            with transaction.atomic():
                # Validate email uniqueness
                if CustomUser.objects.filter(email=user_data['email']).exists():
                    return {'success': False, 'error': 'Email already registered'}
                
                # Validate password strength
                password_validation = self.validate_password_strength(user_data['password'])
                if not password_validation['valid']:
                    return {'success': False, 'error': password_validation['message']}
                
                # Create user
                user = CustomUser.objects.create_user(
                    username=user_data['email'],
                    email=user_data['email'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    company=user_data['company'],
                    phone=user_data.get('phone', ''),
                    country=user_data.get('country', 'CM'),
                    city=user_data.get('city', ''),
                    industry=user_data.get('industry', 'OTHER'),
                    company_size=user_data.get('company_size', '1-5'),
                    role='CLIENT',  # Default role for registration
                    is_active=False,  # Require email verification
                )
                
                # Set additional fields
                user.company_website = user_data.get('company_website', '')
                user.preferred_language = user_data.get('language', 'en')
                user.save()
                
                # Create user profile
                profile = UserProfile.objects.create(
                    user=user,
                    email_marketing_consent=user_data.get('marketing_consent', True),
                    newsletter_subscription=user_data.get('newsletter_subscription', True),
                )
                
                # Generate email verification token
                verification_token = user.generate_email_verification_token()
                
                # Send verification email
                self.send_verification_email(user, verification_token, request)
                
                # Log activity
                UserActivity.log_activity(
                    user=user,
                    activity_type='REGISTRATION',
                    description='User registered',
                    request=request
                )
                
                return {
                    'success': True,
                    'user': user,
                    'message': 'Registration successful. Please check your email to verify your account.'
                }
                
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return {'success': False, 'error': 'Registration failed. Please try again.'}
    
    def validate_password_strength(self, password):
        """Validate password strength"""
        if len(password) < 8:
            return {'valid': False, 'message': 'Password must be at least 8 characters long'}
        
        if not re.search(r'[A-Z]', password):
            return {'valid': False, 'message': 'Password must contain at least one uppercase letter'}
        
        if not re.search(r'[a-z]', password):
            return {'valid': False, 'message': 'Password must contain at least one lowercase letter'}
        
        if not re.search(r'\d', password):
            return {'valid': False, 'message': 'Password must contain at least one number'}
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return {'valid': False, 'message': 'Password must contain at least one special character'}
        
        # Check against common passwords
        common_passwords = [
            'password', '123456', '123456789', 'qwerty', 'abc123',
            'password123', 'admin', 'letmein', 'welcome', 'monkey'
        ]
        if password.lower() in common_passwords:
            return {'valid': False, 'message': 'Password is too common'}
        
        return {'valid': True, 'message': 'Password is strong'}
    
    def authenticate_user(self, email, password, request=None):
        """Authenticate user and handle login"""
        try:
            # Get user by email
            user = CustomUser.objects.get(email=email, is_active=True)
            
            # Check password
            if not user.check_password(password):
                return {'success': False, 'error': 'Invalid email or password'}
            
            # Check if email is verified
            if not user.is_email_verified:
                return {
                    'success': False, 
                    'error': 'Please verify your email before logging in',
                    'requires_verification': True,
                    'user_id': user.id
                }
            
            # Update login information
            user.login_count += 1
            user.last_login = timezone.now()
            if request:
                user.last_login_ip = self.get_client_ip(request)
            user.save(update_fields=['login_count', 'last_login', 'last_login_ip'])
            
            # Log activity
            UserActivity.log_activity(
                user=user,
                activity_type='LOGIN',
                description='User logged in',
                request=request
            )
            
            return {'success': True, 'user': user}
            
        except CustomUser.DoesNotExist:
            return {'success': False, 'error': 'Invalid email or password'}
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return {'success': False, 'error': 'Authentication failed'}
    
    def verify_email(self, token):
        """Verify user email with token"""
        try:
            user = CustomUser.objects.get(
                email_verification_token=token,
                is_active=False
            )
            
            # Check if token is not expired (24 hours)
            if user.email_verification_sent_at:
                expiry_time = user.email_verification_sent_at + timedelta(hours=24)
                if timezone.now() > expiry_time:
                    return {'success': False, 'error': 'Verification token has expired'}
            
            # Verify email
            user.verify_email()
            user.is_active = True
            user.save(update_fields=['is_active'])
            
            # Log activity
            UserActivity.log_activity(
                user=user,
                activity_type='EMAIL_VERIFIED',
                description='Email verified successfully'
            )
            
            return {'success': True, 'user': user}
            
        except CustomUser.DoesNotExist:
            return {'success': False, 'error': 'Invalid verification token'}
        except Exception as e:
            logger.error(f"Email verification error: {str(e)}")
            return {'success': False, 'error': 'Email verification failed'}
    
    def resend_verification_email(self, email, request=None):
        """Resend verification email"""
        try:
            user = CustomUser.objects.get(
                email=email,
                is_email_verified=False
            )
            
            # Check if we can resend (not too frequent)
            if user.email_verification_sent_at:
                time_diff = timezone.now() - user.email_verification_sent_at
                if time_diff < timedelta(minutes=5):
                    return {
                        'success': False, 
                        'error': 'Please wait 5 minutes before requesting another verification email'
                    }
            
            # Generate new token and send email
            verification_token = user.generate_email_verification_token()
            self.send_verification_email(user, verification_token, request)
            
            return {'success': True, 'message': 'Verification email sent'}
            
        except CustomUser.DoesNotExist:
            return {'success': False, 'error': 'User not found or email already verified'}
        except Exception as e:
            logger.error(f"Resend verification error: {str(e)}")
            return {'success': False, 'error': 'Failed to send verification email'}
    
    def initiate_password_reset(self, email, request=None):
        """Initiate password reset process"""
        try:
            user = CustomUser.objects.get(email=email, is_active=True)
            
            # Generate reset token
            reset_token = user.generate_password_reset_token()
            
            # Send reset email
            self.send_password_reset_email(user, reset_token, request)
            
            # Log activity
            UserActivity.log_activity(
                user=user,
                activity_type='PASSWORD_RESET_REQUESTED',
                description='Password reset requested',
                request=request
            )
            
            return {'success': True, 'message': 'Password reset email sent'}
            
        except CustomUser.DoesNotExist:
            # Don't reveal if email exists
            return {'success': True, 'message': 'If the email exists, a reset link has been sent'}
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return {'success': False, 'error': 'Failed to send reset email'}
    
    def reset_password(self, token, new_password):
        """Reset password with token"""
        try:
            user = CustomUser.objects.get(password_reset_token=token)
            
            # Check if token is valid
            if not user.is_password_reset_token_valid():
                return {'success': False, 'error': 'Reset token has expired'}
            
            # Validate new password
            password_validation = self.validate_password_strength(new_password)
            if not password_validation['valid']:
                return {'success': False, 'error': password_validation['message']}
            
            # Set new password
            user.set_password(new_password)
            user.password_reset_token = None
            user.password_reset_sent_at = None
            user.save(update_fields=['password', 'password_reset_token', 'password_reset_sent_at'])
            
            # Log activity
            UserActivity.log_activity(
                user=user,
                activity_type='PASSWORD_CHANGED',
                description='Password reset completed'
            )
            
            return {'success': True, 'user': user}
            
        except CustomUser.DoesNotExist:
            return {'success': False, 'error': 'Invalid reset token'}
        except Exception as e:
            logger.error(f"Password reset completion error: {str(e)}")
            return {'success': False, 'error': 'Password reset failed'}
    
    def change_password(self, user, old_password, new_password):
        """Change user password"""
        try:
            # Verify old password
            if not user.check_password(old_password):
                return {'success': False, 'error': 'Current password is incorrect'}
            
            # Validate new password
            password_validation = self.validate_password_strength(new_password)
            if not password_validation['valid']:
                return {'success': False, 'error': password_validation['message']}
            
            # Set new password
            user.set_password(new_password)
            user.save(update_fields=['password'])
            
            # Log activity
            UserActivity.log_activity(
                user=user,
                activity_type='PASSWORD_CHANGE',
                description='Password changed by user'
            )
            
            return {'success': True, 'message': 'Password changed successfully'}
            
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            return {'success': False, 'error': 'Password change failed'}
    
    def send_verification_email(self, user, token, request=None):
        """Send email verification email"""
        try:
            site_domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
            if request:
                site_domain = request.get_host()
            
            verification_url = f"http{'s' if not settings.DEBUG else ''}://{site_domain}/auth/verify-email/{token}/"
            
            context = {
                'user': user,
                'verification_url': verification_url,
                'site_name': settings.PLATFORM_NAME,
                'token': token,
            }
            
            subject = f"Verify your {settings.PLATFORM_NAME} account"
            
            # Use platform email service
            return self.email_service.send_transactional_email(
                to_email=user.email,
                subject=subject,
                template_name='auth/verification_email.html',
                context=context
            )
            
        except Exception as e:
            logger.error(f"Send verification email error: {str(e)}")
            return False
    
    def send_password_reset_email(self, user, token, request=None):
        """Send password reset email"""
        try:
            site_domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
            if request:
                site_domain = request.get_host()
            
            reset_url = f"http{'s' if not settings.DEBUG else ''}://{site_domain}/auth/password-reset-confirm/{token}/"
            
            context = {
                'user': user,
                'reset_url': reset_url,
                'site_name': settings.PLATFORM_NAME,
                'token': token,
            }
            
            subject = f"Reset your {settings.PLATFORM_NAME} password"
            
            # Use platform email service
            return self.email_service.send_transactional_email(
                to_email=user.email,
                subject=subject,
                template_name='auth/password_reset_email.html',
                context=context
            )
            
        except Exception as e:
            logger.error(f"Send password reset email error: {str(e)}")
            return False
    
    def create_super_admin(self, user_data):
        """Create super admin user"""
        try:
            with transaction.atomic():
                user = CustomUser.objects.create_user(
                    username=user_data['email'],
                    email=user_data['email'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    company=user_data.get('company', 'AfriMail Pro'),
                    role='SUPER_ADMIN',
                    is_active=True,
                    is_email_verified=True,
                    is_staff=True,
                    is_superuser=True,
                )
                
                # Create profile
                UserProfile.objects.create(
                    user=user,
                    max_contacts=999999,
                    max_campaigns_per_month=999999,
                    max_emails_per_month=999999,
                    is_trial=False,
                )
                
                return {'success': True, 'user': user}
                
        except Exception as e:
            logger.error(f"Create super admin error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def logout_user(self, user, request=None):
        """Handle user logout"""
        try:
            # Log activity
            UserActivity.log_activity(
                user=user,
                activity_type='LOGOUT',
                description='User logged out',
                request=request
            )
            
            # Django logout
            if request:
                logout(request)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return {'success': False, 'error': 'Logout failed'}


class SessionManager:
    """Manage user sessions and security"""
    
    @staticmethod
    def is_session_valid(request):
        """Check if session is valid and not expired"""
        if not request.user.is_authenticated:
            return False
        
        # Check session age
        session_age = request.session.get('session_start_time')
        if session_age:
            session_start = timezone.datetime.fromisoformat(session_age)
            if timezone.now() - session_start > timedelta(hours=24):
                return False
        
        return True
    
    @staticmethod
    def initialize_session(request, user):
        """Initialize user session with security data"""
        request.session['session_start_time'] = timezone.now().isoformat()
        request.session['user_id'] = str(user.id)
        request.session['ip_address'] = AuthenticationService.get_client_ip(request)
        request.session['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
    
    @staticmethod
    def validate_session_security(request):
        """Validate session security (IP, user agent)"""
        if not request.user.is_authenticated:
            return False
        
        # Check IP consistency (optional - can be disabled for mobile users)
        stored_ip = request.session.get('ip_address')
        current_ip = AuthenticationService.get_client_ip(request)
        
        # For now, we'll allow IP changes (mobile users, VPNs, etc.)
        # if stored_ip and stored_ip != current_ip:
        #     return False
        
        return True


class PermissionManager:
    """Manage user permissions and access control"""
    
    @staticmethod
    def can_access_admin_panel(user):
        """Check if user can access admin panel"""
        return user.is_authenticated and user.is_super_admin
    
    @staticmethod
    def can_manage_users(user):
        """Check if user can manage other users"""
        return user.is_authenticated and user.is_super_admin
    
    @staticmethod
    def can_view_system_stats(user):
        """Check if user can view system statistics"""
        return user.is_authenticated and user.is_super_admin
    
    @staticmethod
    def can_create_contact(user):
        """Check if user can create contacts"""
        if not user.is_authenticated:
            return False
        
        if user.is_super_admin:
            return True
        
        # Check limits for client users
        profile = getattr(user, 'profile', None)
        if profile:
            return profile.can_create_contact()
        
        return False
    
    @staticmethod
    def can_create_campaign(user):
        """Check if user can create campaigns"""
        if not user.is_authenticated:
            return False
        
        if user.is_super_admin:
            return True
        
        # Check limits for client users
        profile = getattr(user, 'profile', None)
        if profile:
            return profile.can_create_campaign()
        
        return False
    
    @staticmethod
    def can_access_analytics(user):
        """Check if user can access analytics"""
        return user.is_authenticated
    
    @staticmethod
    def can_export_data(user):
        """Check if user can export data"""
        return user.is_authenticated
    
    @staticmethod
    def can_import_contacts(user):
        """Check if user can import contacts"""
        return user.is_authenticated
    
    @staticmethod
    def get_user_permissions(user):
        """Get all permissions for a user"""
        if not user.is_authenticated:
            return []
        
        permissions = [
            'view_dashboard',
            'manage_contacts',
            'create_campaigns',
            'view_analytics',
            'export_data',
            'import_contacts',
            'manage_profile',
        ]
        
        if user.is_super_admin:
            permissions.extend([
                'access_admin_panel',
                'manage_users',
                'view_system_stats',
                'manage_platform_settings',
                'view_email_logs',
            ])
        
        return permissions