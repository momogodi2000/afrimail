
# backend/views/auth_views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import View, TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from ..authentication import AuthenticationService, SessionManager, PermissionManager
from ..models import CustomUser, UserActivity
from ..forms import RegistrationForm, LoginForm, PasswordResetForm, ChangePasswordForm
import json
import logging

logger = logging.getLogger(__name__)


class LoginView(View):
    """User login view"""
    
    template_name = 'auth/login.html'
    form_class = LoginForm
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(self.get_success_url(request.user))
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            auth_service = AuthenticationService()
            result = auth_service.authenticate_user(email, password, request)
            
            if result['success']:
                user = result['user']
                login(request, user)
                
                # Set session expiry
                if not remember_me:
                    request.session.set_expiry(0)  # Browser close
                else:
                    request.session.set_expiry(1209600)  # 2 weeks
                
                # Initialize session
                SessionManager.initialize_session(request, user)
                
                messages.success(request, f'Welcome back, {user.get_short_name()}!')
                return redirect(self.get_success_url(user))
            
            elif result.get('requires_verification'):
                messages.warning(
                    request, 
                    'Please verify your email before logging in. '
                    '<a href="/auth/resend-verification/">Resend verification email</a>'
                )
            else:
                messages.error(request, result['error'])
        
        return render(request, self.template_name, {'form': form})
    
    def get_success_url(self, user):
        """Get redirect URL after successful login"""
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        
        return user.get_dashboard_url()


class LogoutView(View):
    """User logout view"""
    
    def get(self, request):
        if request.user.is_authenticated:
            auth_service = AuthenticationService()
            auth_service.logout_user(request.user, request)
        
        messages.success(request, 'You have been logged out successfully.')
        return redirect('backend:login')


class RegisterView(View):
    """User registration view"""
    
    template_name = 'auth/register.html'
    form_class = RegistrationForm
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('backend:dashboard')
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            auth_service = AuthenticationService()
            result = auth_service.register_user(form.cleaned_data, request)
            
            if result['success']:
                messages.success(
                    request,
                    'Registration successful! Please check your email to verify your account.'
                )
                return redirect('backend:login')
            else:
                messages.error(request, result['error'])
        
        return render(request, self.template_name, {'form': form})


class VerifyEmailView(View):
    """Email verification view"""
    
    def get(self, request, token):
        auth_service = AuthenticationService()
        result = auth_service.verify_email(token)
        
        if result['success']:
            messages.success(
                request,
                'Your email has been verified successfully! You can now log in.'
            )
            return redirect('backend:login')
        else:
            messages.error(request, result['error'])
            return redirect('backend:register')


class PasswordResetView(View):
    """Password reset request view"""
    
    template_name = 'auth/password_reset.html'
    form_class = PasswordResetForm
    
    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            email = form.cleaned_data['email']
            auth_service = AuthenticationService()
            result = auth_service.initiate_password_reset(email, request)
            
            messages.success(
                request,
                'If an account with this email exists, you will receive password reset instructions.'
            )
            return redirect('backend:login')
        
        return render(request, self.template_name, {'form': form})


class PasswordResetConfirmView(View):
    """Password reset confirmation view"""
    
    template_name = 'auth/password_reset_confirm.html'
    
    def get(self, request, token):
        # Verify token exists and is valid
        try:
            user = CustomUser.objects.get(password_reset_token=token)
            if not user.is_password_reset_token_valid():
                messages.error(request, 'Password reset token has expired.')
                return redirect('backend:password_reset')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Invalid password reset token.')
            return redirect('backend:password_reset')
        
        return render(request, self.template_name, {'token': token})
    
    def post(self, request, token):
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, self.template_name, {'token': token})
        
        auth_service = AuthenticationService()
        result = auth_service.reset_password(token, password)
        
        if result['success']:
            messages.success(
                request,
                'Your password has been reset successfully! You can now log in.'
            )
            return redirect('backend:login')
        else:
            messages.error(request, result['error'])
            return render(request, self.template_name, {'token': token})


@method_decorator(login_required, name='dispatch')
class ProfileView(View):
    """User profile view"""
    
    template_name = 'auth/profile.html'
    
    def get(self, request):
        context = {
            'user': request.user,
            'profile': getattr(request.user, 'profile', None),
            'recent_activities': request.user.activities.all()[:10],
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        # Handle profile updates
        user = request.user
        profile = getattr(user, 'profile', None)
        
        # Update user fields
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.phone = request.POST.get('phone', user.phone)
        user.company = request.POST.get('company', user.company)
        user.company_website = request.POST.get('company_website', user.company_website)
        user.city = request.POST.get('city', user.city)
        user.country = request.POST.get('country', user.country)
        user.industry = request.POST.get('industry', user.industry)
        user.company_size = request.POST.get('company_size', user.company_size)
        user.preferred_language = request.POST.get('preferred_language', user.preferred_language)
        user.timezone = request.POST.get('timezone', user.timezone)
        user.receive_notifications = request.POST.get('receive_notifications') == 'on'
        user.save()
        
        # Update profile fields
        if profile:
            profile.bio = request.POST.get('bio', profile.bio)
            profile.email_signature = request.POST.get('email_signature', profile.email_signature)
            profile.items_per_page = int(request.POST.get('items_per_page', profile.items_per_page))
            profile.dashboard_layout = request.POST.get('dashboard_layout', profile.dashboard_layout)
            profile.email_marketing_consent = request.POST.get('email_marketing_consent') == 'on'
            profile.newsletter_subscription = request.POST.get('newsletter_subscription') == 'on'
            profile.save()
        
        # Log activity
        UserActivity.log_activity(
            user=user,
            activity_type='PROFILE_UPDATED',
            description='Profile information updated',
            request=request
        )
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('backend:profile')


@method_decorator(login_required, name='dispatch')
class ChangePasswordView(View):
    """Change password view"""
    
    template_name = 'auth/change_password.html'
    form_class = ChangePasswordForm
    
    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            auth_service = AuthenticationService()
            result = auth_service.change_password(
                user=request.user,
                old_password=form.cleaned_data['old_password'],
                new_password=form.cleaned_data['new_password']
            )
            
            if result['success']:
                messages.success(request, 'Password changed successfully!')
                return redirect('backend:profile')
            else:
                messages.error(request, result['error'])
        
        return render(request, self.template_name, {'form': form})


# AJAX Views for authentication
class ResendVerificationEmailView(View):
    """Resend email verification"""
    
    def post(self, request):
        email = request.POST.get('email')
        
        if not email:
            return JsonResponse({'success': False, 'error': 'Email is required'})
        
        auth_service = AuthenticationService()
        result = auth_service.resend_verification_email(email, request)
        
        return JsonResponse(result)


@method_decorator(csrf_exempt, name='dispatch')
class CheckEmailAvailabilityView(View):
    """Check if email is available for registration"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({'available': False, 'error': 'Email is required'})
            
            # Check if email exists
            exists = CustomUser.objects.filter(email=email).exists()
            
            return JsonResponse({
                'available': not exists,
                'message': 'Email is available' if not exists else 'Email is already registered'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'available': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Email availability check error: {str(e)}")
            return JsonResponse({'available': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
class UserSettingsAPIView(View):
    """API view for user settings"""
    
    def get(self, request):
        """Get user settings"""
        user = request.user
        profile = getattr(user, 'profile', None)
        
        settings_data = {
            'user': {
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'company': user.company,
                'phone': user.phone,
                'country': user.country,
                'city': user.city,
                'industry': user.industry,
                'company_size': user.company_size,
                'preferred_language': user.preferred_language,
                'timezone': user.timezone,
                'receive_notifications': user.receive_notifications,
            },
            'profile': {
                'bio': profile.bio if profile else '',
                'email_signature': profile.email_signature if profile else '',
                'items_per_page': profile.items_per_page if profile else 20,
                'dashboard_layout': profile.dashboard_layout if profile else 'default',
                'email_marketing_consent': profile.email_marketing_consent if profile else True,
                'newsletter_subscription': profile.newsletter_subscription if profile else True,
            } if profile else {},
            'permissions': PermissionManager.get_user_permissions(user),
        }
        
        return JsonResponse(settings_data)
    
    def post(self, request):
        """Update user settings"""
        try:
            data = json.loads(request.body)
            user = request.user
            profile = getattr(user, 'profile', None)
            
            # Update user fields
            user_data = data.get('user', {})
            for field in ['first_name', 'last_name', 'phone', 'company', 'city', 'country', 'industry', 'company_size', 'preferred_language', 'timezone']:
                if field in user_data:
                    setattr(user, field, user_data[field])
            
            if 'receive_notifications' in user_data:
                user.receive_notifications = user_data['receive_notifications']
            
            user.save()
            
            # Update profile fields
            if profile:
                profile_data = data.get('profile', {})
                for field in ['bio', 'email_signature', 'items_per_page', 'dashboard_layout']:
                    if field in profile_data:
                        setattr(profile, field, profile_data[field])
                
                if 'email_marketing_consent' in profile_data:
                    profile.email_marketing_consent = profile_data['email_marketing_consent']
                
                if 'newsletter_subscription' in profile_data:
                    profile.newsletter_subscription = profile_data['newsletter_subscription']
                
                profile.save()
            
            # Log activity
            UserActivity.log_activity(
                user=user,
                activity_type='PROFILE_UPDATED',
                description='Profile updated via API',
                request=request
            )
            
            return JsonResponse({'success': True, 'message': 'Settings updated successfully'})
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Settings update error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


# Security and Session Views
@method_decorator(login_required, name='dispatch')
class SecurityView(TemplateView):
    """Security settings view"""
    
    template_name = 'auth/security.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context.update({
            'user': user,
            'recent_activities': user.activities.all()[:20],
            'active_sessions': self.get_active_sessions(),
            'login_history': user.activities.filter(
                activity_type='LOGIN'
            ).order_by('-created_at')[:10],
        })
        
        return context
    
    def get_active_sessions(self):
        """Get active sessions for the user (simplified)"""
        # In a real implementation, you'd track sessions in the database
        # For now, return current session info
        return [{
            'session_key': self.request.session.session_key,
            'ip_address': self.request.session.get('ip_address', 'Unknown'),
            'user_agent': self.request.META.get('HTTP_USER_AGENT', 'Unknown'),
            'created_at': timezone.now(),
            'is_current': True,
        }]


@method_decorator(login_required, name='dispatch')
class TwoFactorSetupView(TemplateView):
    """Two-factor authentication setup (future feature)"""
    
    template_name = 'auth/two_factor_setup.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # This would contain 2FA setup logic
        context['two_factor_enabled'] = False  # Future implementation
        return context