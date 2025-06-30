# backend/views/campaign_views.py

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
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging

from ..models import (
    EmailCampaign, EmailTemplate, ContactList, EmailDomainConfig,
    EmailEvent, EmailQueue, Contact
)
from ..forms import EmailCampaignForm, EmailTemplateForm, CampaignSearchForm
from ..services import CampaignService, EmailService
from ..authentication import PermissionManager

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class CampaignListView(ListView):
    """List all campaigns for the user"""
    
    model = EmailCampaign
    template_name = 'campaigns/campaign_list.html'
    context_object_name = 'campaigns'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = EmailCampaign.objects.filter(user=self.request.user).order_by('-created_at')
        
        # Apply search filters
        search_form = CampaignSearchForm(self.request.GET)
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            status = search_form.cleaned_data.get('status')
            campaign_type = search_form.cleaned_data.get('campaign_type')
            date_from = search_form.cleaned_data.get('date_from')
            date_to = search_form.cleaned_data.get('date_to')
            
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(subject__icontains=search) |
                    Q(description__icontains=search)
                )
            
            if status:
                queryset = queryset.filter(status=status)
            
            if campaign_type:
                queryset = queryset.filter(campaign_type=campaign_type)
            
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add search form
        context['search_form'] = CampaignSearchForm(self.request.GET)
        
        # Add summary statistics
        user_campaigns = EmailCampaign.objects.filter(user=self.request.user)
        context['stats'] = {
            'total_campaigns': user_campaigns.count(),
            'draft_campaigns': user_campaigns.filter(status='DRAFT').count(),
            'sending_campaigns': user_campaigns.filter(status='SENDING').count(),
            'sent_campaigns': user_campaigns.filter(status='SENT').count(),
            'failed_campaigns': user_campaigns.filter(status='FAILED').count(),
        }
        
        return context


@method_decorator(login_required, name='dispatch')
class CampaignCreateView(CreateView):
    """Create a new campaign"""
    
    model = EmailCampaign
    form_class = EmailCampaignForm
    template_name = 'campaigns/campaign_create.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Check if user can create campaigns
        if not PermissionManager.can_create_campaign(self.request.user):
            messages.error(self.request, 'You have reached your campaign creation limit.')
            return redirect('backend:campaign_list')
        
        form.instance.user = self.request.user
        
        # Set from_email from email_config if not provided
        if form.instance.email_config and not form.instance.from_email:
            form.instance.from_email = form.instance.email_config.from_email
        
        # Set from_name if not provided
        if form.instance.email_config and not form.instance.from_name:
            form.instance.from_name = form.instance.email_config.from_name
        
        campaign = form.save()
        
        # Calculate recipient count
        campaign.calculate_recipient_count()
        
        # Check if user wants to send immediately
        if 'save_and_send' in self.request.POST:
            return redirect('backend:campaign_send', pk=campaign.pk)
        
        messages.success(self.request, f'Campaign "{campaign.name}" created successfully!')
        return redirect('backend:campaign_detail', pk=campaign.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add available templates
        context['templates'] = EmailTemplate.objects.filter(
            Q(user=self.request.user) | Q(is_shared=True),
            is_active=True
        ).order_by('-created_at')
        
        return context


@method_decorator(login_required, name='dispatch')
class CampaignDetailView(DetailView):
    """Campaign detail view"""
    
    model = EmailCampaign
    template_name = 'campaigns/campaign_detail.html'
    context_object_name = 'campaign'
    
    def get_queryset(self):
        return EmailCampaign.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = self.object
        
        # Get campaign statistics
        campaign_service = CampaignService()
        context['stats'] = campaign_service.get_campaign_statistics(campaign)
        context['timeline'] = campaign_service.get_campaign_timeline(campaign)
        
        # Get recent events
        context['recent_events'] = EmailEvent.objects.filter(
            campaign=campaign
        ).order_by('-created_at')[:10]
        
        # Get pending queue items
        context['pending_emails'] = EmailQueue.objects.filter(
            campaign=campaign,
            status='PENDING'
        ).count()
        
        # Get failed queue items
        context['failed_emails'] = EmailQueue.objects.filter(
            campaign=campaign,
            status='FAILED'
        ).count()
        
        return context


@method_decorator(login_required, name='dispatch')
class CampaignUpdateView(UpdateView):
    """Update campaign"""
    
    model = EmailCampaign
    form_class = EmailCampaignForm
    template_name = 'campaigns/campaign_update.html'
    
    def get_queryset(self):
        return EmailCampaign.objects.filter(user=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Only allow editing of draft campaigns
        if self.object.status != 'DRAFT':
            messages.error(self.request, 'Only draft campaigns can be edited.')
            return redirect('backend:campaign_detail', pk=self.object.pk)
        
        # Recalculate recipient count
        campaign = form.save()
        campaign.calculate_recipient_count()
        
        messages.success(self.request, f'Campaign "{campaign.name}" updated successfully!')
        return redirect('backend:campaign_detail', pk=campaign.pk)


@method_decorator(login_required, name='dispatch')
class CampaignDeleteView(DeleteView):
    """Delete campaign"""
    
    model = EmailCampaign
    template_name = 'campaigns/campaign_delete.html'
    success_url = reverse_lazy('backend:campaign_list')
    
    def get_queryset(self):
        return EmailCampaign.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        campaign = self.get_object()
        
        # Only allow deletion of draft or failed campaigns
        if campaign.status not in ['DRAFT', 'FAILED', 'CANCELLED']:
            messages.error(request, 'Cannot delete campaigns that have been sent or are currently sending.')
            return redirect('backend:campaign_detail', pk=campaign.pk)
        
        messages.success(request, f'Campaign "{campaign.name}" deleted successfully!')
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class CampaignSendView(TemplateView):
    """Send campaign confirmation and execution"""
    
    template_name = 'campaigns/campaign_send.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = get_object_or_404(
            EmailCampaign,
            pk=kwargs['pk'],
            user=self.request.user
        )
        context['campaign'] = campaign
        
        # Validate campaign for sending
        campaign_service = CampaignService()
        validation = campaign_service.validate_campaign_for_sending(campaign)
        context['validation'] = validation
        
        return context
    
    def post(self, request, pk):
        campaign = get_object_or_404(
            EmailCampaign,
            pk=pk,
            user=request.user
        )
        
        # Send campaign
        campaign_service = CampaignService()
        result = campaign_service.send_campaign(campaign)
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('backend:campaign_detail', pk=campaign.pk)
        else:
            messages.error(request, result['error'])
            return redirect('backend:campaign_send', pk=campaign.pk)


@method_decorator(login_required, name='dispatch')
class CampaignPreviewView(DetailView):
    """Preview campaign email"""
    
    model = EmailCampaign
    template_name = 'campaigns/campaign_preview.html'
    
    def get_queryset(self):
        return EmailCampaign.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = self.object
        
        # Get a sample contact for personalization preview
        sample_contact = Contact.objects.filter(
            user=self.request.user,
            is_active=True
        ).first()
        
        if sample_contact:
            # Personalize content with sample contact
            email_service = EmailService()
            personalized_html = email_service._personalize_content(
                campaign.html_content, sample_contact
            )
            personalized_subject = email_service._personalize_content(
                campaign.subject, sample_contact
            )
            
            context['personalized_html'] = personalized_html
            context['personalized_subject'] = personalized_subject
            context['sample_contact'] = sample_contact
        
        return context


@method_decorator(login_required, name='dispatch')
class CampaignDuplicateView(View):
    """Duplicate a campaign"""
    
    def post(self, request, pk):
        campaign = get_object_or_404(
            EmailCampaign,
            pk=pk,
            user=request.user
        )
        
        campaign_service = CampaignService()
        result = campaign_service.duplicate_campaign(campaign)
        
        if result['success']:
            messages.success(request, f'Campaign duplicated successfully!')
            return redirect('backend:campaign_detail', pk=result['campaign'].pk)
        else:
            messages.error(request, result['error'])
            return redirect('backend:campaign_detail', pk=campaign.pk)


@method_decorator(login_required, name='dispatch')
class CampaignAnalyticsView(DetailView):
    """Detailed campaign analytics"""
    
    model = EmailCampaign
    template_name = 'campaigns/campaign_analytics.html'
    
    def get_queryset(self):
        return EmailCampaign.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = self.object
        
        # Get detailed analytics
        from ..services.analytics_service import AnalyticsService
        analytics_service = AnalyticsService()
        context['analytics'] = analytics_service.get_campaign_detailed_analytics(campaign)
        
        # Get top performing contacts
        top_contacts = EmailEvent.objects.filter(
            campaign=campaign,
            event_type__in=['OPENED', 'CLICKED']
        ).values(
            'contact__email',
            'contact__first_name',
            'contact__last_name'
        ).annotate(
            opens=Count('id', filter=Q(event_type='OPENED')),
            clicks=Count('id', filter=Q(event_type='CLICKED'))
        ).order_by('-opens', '-clicks')[:10]
        
        context['top_contacts'] = top_contacts
        
        return context


# Template Views
@method_decorator(login_required, name='dispatch')
class TemplateListView(ListView):
    """List email templates"""
    
    model = EmailTemplate
    template_name = 'campaigns/template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def get_queryset(self):
        return EmailTemplate.objects.filter(
            Q(user=self.request.user) | Q(is_shared=True),
            is_active=True
        ).order_by('-created_at')


@method_decorator(login_required, name='dispatch')
class TemplateCreateView(CreateView):
    """Create email template"""
    
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'campaigns/template_create.html'
    success_url = reverse_lazy('backend:template_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, f'Template "{form.instance.name}" created successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class TemplateUpdateView(UpdateView):
    """Update email template"""
    
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'campaigns/template_update.html'
    success_url = reverse_lazy('backend:template_list')
    
    def get_queryset(self):
        return EmailTemplate.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, f'Template "{form.instance.name}" updated successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class TemplateDeleteView(DeleteView):
    """Delete email template"""
    
    model = EmailTemplate
    template_name = 'campaigns/template_delete.html'
    success_url = reverse_lazy('backend:template_list')
    
    def get_queryset(self):
        return EmailTemplate.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        template = self.get_object()
        messages.success(request, f'Template "{template.name}" deleted successfully!')
        return super().delete(request, *args, **kwargs)


# AJAX Views
@method_decorator(login_required, name='dispatch')
class CampaignStatsAjaxView(View):
    """Get campaign statistics via AJAX"""
    
    def get(self, request):
        campaign_id = request.GET.get('campaign_id')
        
        if not campaign_id:
            return JsonResponse({'error': 'Campaign ID required'}, status=400)
        
        try:
            campaign = EmailCampaign.objects.get(
                id=campaign_id,
                user=request.user
            )
            
            stats = {
                'emails_sent': campaign.emails_sent,
                'emails_delivered': campaign.emails_delivered,
                'unique_opens': campaign.unique_opens,
                'unique_clicks': campaign.unique_clicks,
                'unsubscribes': campaign.unsubscribes,
                'bounces': campaign.emails_bounced,
                'open_rate': campaign.open_rate,
                'click_rate': campaign.click_rate,
                'status': campaign.status,
            }
            
            return JsonResponse(stats)
            
        except EmailCampaign.DoesNotExist:
            return JsonResponse({'error': 'Campaign not found'}, status=404)


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class CampaignActionView(View):
    """Handle campaign actions (pause, resume, cancel)"""
    
    def post(self, request, pk):
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            campaign = get_object_or_404(
                EmailCampaign,
                pk=pk,
                user=request.user
            )
            
            campaign_service = CampaignService()
            
            if action == 'pause':
                result = campaign_service.pause_campaign(campaign)
            elif action == 'resume':
                result = campaign_service.resume_campaign(campaign)
            elif action == 'cancel':
                result = campaign_service.cancel_campaign(campaign)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Campaign action error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class LoadTemplateAjaxView(View):
    """Load template content via AJAX"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            template_id = data.get('template_id')
            
            if not template_id:
                return JsonResponse({'error': 'Template ID required'}, status=400)
            
            template = get_object_or_404(
                EmailTemplate,
                id=template_id,
                user=request.user
            )
            
            return JsonResponse({
                'success': True,
                'subject': template.subject,
                'html_content': template.html_content,
                'text_content': template.text_content or '',
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Load template error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
class CampaignQueueStatusView(View):
    """Get campaign queue status"""
    
    def get(self, request, pk):
        try:
            campaign = get_object_or_404(
                EmailCampaign,
                pk=pk,
                user=request.user
            )
            
            queue_stats = {
                'pending': EmailQueue.objects.filter(
                    campaign=campaign,
                    status='PENDING'
                ).count(),
                'sending': EmailQueue.objects.filter(
                    campaign=campaign,
                    status='SENDING'
                ).count(),
                'sent': EmailQueue.objects.filter(
                    campaign=campaign,
                    status='SENT'
                ).count(),
                'failed': EmailQueue.objects.filter(
                    campaign=campaign,
                    status='FAILED'
                ).count(),
                'retrying': EmailQueue.objects.filter(
                    campaign=campaign,
                    status='RETRYING'
                ).count(),
            }
            
            return JsonResponse({
                'success': True,
                'queue_stats': queue_stats,
                'campaign_status': campaign.status,
            })
            
        except Exception as e:
            logger.error(f"Queue status error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
class SendTestEmailView(View):
    """Send test email for campaign"""
    
    def post(self, request, pk):
        try:
            data = json.loads(request.body)
            test_email = data.get('email')
            
            if not test_email:
                return JsonResponse({'success': False, 'error': 'Email address required'})
            
            campaign = get_object_or_404(
                EmailCampaign,
                pk=pk,
                user=request.user
            )
            
            # Send test email
            email_service = EmailService()
            result = email_service.send_email(
                to_email=test_email,
                subject=f"[TEST] {campaign.subject}",
                html_content=campaign.html_content,
                text_content=campaign.text_content,
                from_email=campaign.from_email,
                from_name=campaign.from_name,
                email_config=campaign.email_config
            )
            
            if result:
                return JsonResponse({
                    'success': True,
                    'message': f'Test email sent to {test_email}'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to send test email'
                })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Send test email error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})