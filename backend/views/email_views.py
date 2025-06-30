# backend/views/email_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import json
import logging

from ..models import EmailDomainConfig
from ..forms import EmailDomainConfigForm
from ..services.email_service import EmailService

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class EmailConfigListView(ListView):
    """List all email domain configurations for the user"""
    
    model = EmailDomainConfig
    template_name = 'email_config/email_config_list.html'
    context_object_name = 'email_configs'
    paginate_by = 20
    
    def get_queryset(self):
        return EmailDomainConfig.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add summary statistics
        context['stats'] = {
            'total_configs': self.get_queryset().count(),
            'verified_configs': self.get_queryset().filter(domain_verified=True).count(),
            'pending_verification': self.get_queryset().filter(domain_verified=False).count(),
            'default_config': self.get_queryset().filter(is_default=True).first(),
        }
        
        return context


@method_decorator(login_required, name='dispatch')
class EmailConfigCreateView(CreateView):
    """Create email domain configuration"""
    
    model = EmailDomainConfig
    form_class = EmailDomainConfigForm
    template_name = 'email_config/email_config_create.html'
    success_url = reverse_lazy('backend:email_config_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # Generate verification token
        import uuid
        form.instance.verification_token = str(uuid.uuid4())
        
        result = super().form_valid(form)
        
        messages.success(
            self.request, 
            f'Email configuration for "{form.instance.domain_name}" created successfully! '
            'Please verify your domain to start sending emails.'
        )
        
        return result
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Add Email Configuration'
        return context


@method_decorator(login_required, name='dispatch')
class EmailConfigDetailView(DetailView):
    """View email domain configuration details"""
    
    model = EmailDomainConfig
    template_name = 'email_config/email_config_detail.html'
    context_object_name = 'email_config'
    
    def get_queryset(self):
        return EmailDomainConfig.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        email_config = self.object
        
        # DNS records for display
        context['dns_records'] = {
            'spf': email_config.spf_record or f'v=spf1 include:_spf.google.com ~all',
            'dkim': email_config.dkim_record or f'Generated after domain verification',
            'dmarc': email_config.dmarc_record or f'v=DMARC1; p=none; rua=mailto:dmarc@{email_config.domain_name}',
        }
        
        # Usage statistics for the last 30 days
        from datetime import timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # This would be calculated from EmailEvent model
        context['usage_stats'] = {
            'emails_sent_30_days': 0,  # TODO: Calculate from EmailEvent
            'emails_remaining_today': max(0, email_config.daily_send_limit - email_config.emails_sent_today),
            'emails_remaining_month': max(0, email_config.monthly_send_limit - email_config.emails_sent_this_month),
        }
        
        return context


@method_decorator(login_required, name='dispatch')
class EmailConfigUpdateView(UpdateView):
    """Update email domain configuration"""
    
    model = EmailDomainConfig
    form_class = EmailDomainConfigForm
    template_name = 'email_config/email_config_update.html'
    success_url = reverse_lazy('backend:email_config_list')
    
    def get_queryset(self):
        return EmailDomainConfig.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        # If domain name changed, reset verification
        if 'domain_name' in form.changed_data:
            form.instance.domain_verified = False
            form.instance.verification_status = 'PENDING'
            form.instance.verification_attempts = 0
            
            # Generate new verification token
            import uuid
            form.instance.verification_token = str(uuid.uuid4())
        
        result = super().form_valid(form)
        
        messages.success(
            self.request, 
            f'Email configuration for "{form.instance.domain_name}" updated successfully!'
        )
        
        return result
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Edit {self.object.domain_name}'
        return context


@method_decorator(login_required, name='dispatch')
class EmailConfigDeleteView(DeleteView):
    """Delete email domain configuration"""
    
    model = EmailDomainConfig
    template_name = 'email_config/email_config_delete.html'
    success_url = reverse_lazy('backend:email_config_list')
    
    def get_queryset(self):
        return EmailDomainConfig.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        email_config = self.get_object()
        domain_name = email_config.domain_name
        
        # Soft delete - mark as inactive instead of actually deleting
        email_config.is_active = False
        email_config.save()
        
        messages.success(
            request, 
            f'Email configuration for "{domain_name}" has been deleted.'
        )
        
        return redirect(self.success_url)


@method_decorator(login_required, name='dispatch')
class EmailConfigVerifyView(DetailView):
    """Verify email domain configuration"""
    
    model = EmailDomainConfig
    template_name = 'email_config/email_config_verify.html'
    context_object_name = 'email_config'
    
    def get_queryset(self):
        return EmailDomainConfig.objects.filter(user=self.request.user)
    
    def post(self, request, *args, **kwargs):
        """Handle domain verification attempt"""
        email_config = self.get_object()
        
        try:
            # Use EmailService to verify domain
            email_service = EmailService()
            verification_result = email_service.verify_domain(email_config)
            
            if verification_result.get('success'):
                email_config.domain_verified = True
                email_config.verification_status = 'VERIFIED'
                email_config.last_verification_attempt = timezone.now()
                email_config.save()
                
                messages.success(
                    request,
                    f'Domain "{email_config.domain_name}" has been successfully verified!'
                )
                
                return redirect('backend:email_config_detail', pk=email_config.pk)
            else:
                email_config.verification_attempts += 1
                email_config.verification_status = 'FAILED'
                email_config.last_verification_attempt = timezone.now()
                email_config.save()
                
                messages.error(
                    request,
                    f'Domain verification failed: {verification_result.get("error", "Unknown error")}'
                )
        
        except Exception as e:
            logger.error(f"Domain verification error for {email_config.domain_name}: {str(e)}")
            messages.error(
                request,
                'An error occurred during domain verification. Please try again later.'
            )
        
        return self.get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        email_config = self.object
        
        # Verification instructions
        context['verification_instructions'] = {
            'txt_record': {
                'name': f'_afrimail-verification.{email_config.domain_name}',
                'value': email_config.verification_token,
                'type': 'TXT'
            },
            'dns_records': {
                'spf': f'v=spf1 include:_spf.google.com ~all',
                'dkim': f'Generated after successful verification',
                'dmarc': f'v=DMARC1; p=none; rua=mailto:dmarc@{email_config.domain_name}'
            }
        }
        
        return context


@method_decorator(login_required, name='dispatch')
class EmailConfigTestView(DetailView):
    """Test email domain configuration"""
    
    model = EmailDomainConfig
    template_name = 'email_config/email_config_test.html'
    context_object_name = 'email_config'
    
    def get_queryset(self):
        return EmailDomainConfig.objects.filter(user=self.request.user)
    
    def post(self, request, *args, **kwargs):
        """Send test email"""
        email_config = self.get_object()
        test_email = request.POST.get('test_email', request.user.email)
        
        try:
            # Use EmailService to send test email
            email_service = EmailService()
            result = email_service.send_test_email(email_config, test_email)
            
            if result.get('success'):
                messages.success(
                    request,
                    f'Test email sent successfully to {test_email}!'
                )
            else:
                messages.error(
                    request,
                    f'Failed to send test email: {result.get("error", "Unknown error")}'
                )
        
        except Exception as e:
            logger.error(f"Test email error for {email_config.domain_name}: {str(e)}")
            messages.error(
                request,
                'An error occurred while sending the test email. Please check your configuration.'
            )
        
        return self.get(request, *args, **kwargs)


# AJAX Views for dynamic functionality
@method_decorator(login_required, name='dispatch')
class DomainVerifyAjaxView(View):
    """AJAX endpoint for domain verification"""
    
    def post(self, request):
        try:
            config_id = request.POST.get('config_id')
            email_config = get_object_or_404(
                EmailDomainConfig,
                id=config_id,
                user=request.user
            )
            
            # Use EmailService to verify domain
            email_service = EmailService()
            result = email_service.verify_domain(email_config)
            
            if result.get('success'):
                email_config.domain_verified = True
                email_config.verification_status = 'VERIFIED'
                email_config.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Domain verified successfully!'
                })
            else:
                email_config.verification_attempts += 1
                email_config.verification_status = 'FAILED'
                email_config.save()
                
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Verification failed')
                })
        
        except Exception as e:
            logger.error(f"AJAX domain verification error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Server error occurred'
            })


@method_decorator(login_required, name='dispatch')
class EmailTestAjaxView(View):
    """AJAX endpoint for sending test emails"""
    
    def post(self, request):
        try:
            config_id = request.POST.get('config_id')
            test_email = request.POST.get('test_email', request.user.email)
            
            email_config = get_object_or_404(
                EmailDomainConfig,
                id=config_id,
                user=request.user
            )
            
            # Use EmailService to send test email
            email_service = EmailService()
            result = email_service.send_test_email(email_config, test_email)
            
            if result.get('success'):
                return JsonResponse({
                    'success': True,
                    'message': f'Test email sent to {test_email}!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Failed to send test email')
                })
        
        except Exception as e:
            logger.error(f"AJAX test email error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Server error occurred'
            })