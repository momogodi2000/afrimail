# backend/views/contact_views.py

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
import csv
import logging
from datetime import timedelta

from ..models import (
    Contact, ContactList, ContactTag, ContactImport,
    EmailEvent, EmailCampaign
)
from ..forms import (
    ContactForm, ContactListForm, ContactImportForm, ContactSearchForm
)
from ..services import ContactService
from ..authentication import PermissionManager

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class ContactListView(ListView):
    """List all contacts for the user"""
    
    model = Contact
    template_name = 'contacts/contact_list.html'
    context_object_name = 'contacts'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Contact.objects.filter(user=self.request.user, is_active=True).order_by('-created_at')
        
        # Apply search filters
        search_form = ContactSearchForm(self.request.user, self.request.GET)
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            status = search_form.cleaned_data.get('status')
            contact_list = search_form.cleaned_data.get('contact_list')
            country = search_form.cleaned_data.get('country')
            
            if search:
                queryset = queryset.filter(
                    Q(email__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(company__icontains=search)
                )
            
            if status:
                queryset = queryset.filter(status=status)
            
            if contact_list:
                queryset = queryset.filter(lists=contact_list)
            
            if country:
                queryset = queryset.filter(country__icontains=country)
        
        return queryset.select_related().prefetch_related('lists', 'tags')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add search form
        context['search_form'] = ContactSearchForm(self.request.user, self.request.GET)
        
        # Add summary statistics
        user_contacts = Contact.objects.filter(user=self.request.user, is_active=True)
        context['stats'] = {
            'total_contacts': user_contacts.count(),
            'active_contacts': user_contacts.filter(status='ACTIVE').count(),
            'unsubscribed_contacts': user_contacts.filter(status='UNSUBSCRIBED').count(),
            'bounced_contacts': user_contacts.filter(status='BOUNCED').count(),
            'new_contacts_today': user_contacts.filter(
                created_at__date=timezone.now().date()
            ).count(),
        }
        
        # Add contact lists for bulk operations
        context['contact_lists'] = ContactList.objects.filter(
            user=self.request.user,
            is_active=True
        )
        
        # Add tags for bulk operations
        context['contact_tags'] = ContactTag.objects.filter(user=self.request.user)
        
        return context


@method_decorator(login_required, name='dispatch')
class ContactCreateView(CreateView):
    """Create a new contact"""
    
    model = Contact
    form_class = ContactForm
    template_name = 'contacts/contact_create.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Check if user can create contacts
        if not PermissionManager.can_create_contact(self.request.user):
            messages.error(self.request, 'You have reached your contact limit.')
            return redirect('backend:contact_list')
        
        form.instance.user = self.request.user
        
        # Check for duplicate email
        if Contact.objects.filter(
            user=self.request.user,
            email=form.instance.email
        ).exists():
            messages.error(self.request, 'A contact with this email already exists.')
            return self.form_invalid(form)
        
        contact = form.save()
        
        # Update list counts
        for contact_list in contact.lists.all():
            contact_list.update_contact_count()
        
        messages.success(self.request, f'Contact "{contact.get_full_name()}" created successfully!')
        return redirect('backend:contact_detail', pk=contact.pk)


@method_decorator(login_required, name='dispatch')
class ContactDetailView(DetailView):
    """Contact detail view"""
    
    model = Contact
    template_name = 'contacts/contact_detail.html'
    context_object_name = 'contact'
    
    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self.object
        
        # Get email history
        context['email_events'] = EmailEvent.objects.filter(
            contact=contact
        ).order_by('-created_at')[:20]
        
        # Get campaigns this contact received
        context['campaigns_received'] = EmailCampaign.objects.filter(
            events__contact=contact
        ).distinct().order_by('-created_at')[:10]
        
        # Get engagement metrics
        context['engagement_metrics'] = {
            'total_emails_received': contact.total_emails_received,
            'total_emails_opened': contact.total_emails_opened,
            'total_emails_clicked': contact.total_emails_clicked,
            'engagement_score': contact.engagement_score,
            'open_rate': contact.open_rate,
            'click_rate': contact.click_rate,
            'last_engagement': contact.last_email_opened_at or contact.last_email_clicked_at,
        }
        
        # Get recent activity timeline
        recent_events = EmailEvent.objects.filter(
            contact=contact
        ).order_by('-created_at')[:10]
        
        context['activity_timeline'] = [{
            'event_type': event.event_type,
            'campaign_name': event.campaign.name,
            'created_at': event.created_at,
            'metadata': event.event_data,
        } for event in recent_events]
        
        return context


@method_decorator(login_required, name='dispatch')
class ContactUpdateView(UpdateView):
    """Update contact"""
    
    model = Contact
    form_class = ContactForm
    template_name = 'contacts/contact_update.html'
    
    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Check for duplicate email (excluding current contact)
        if Contact.objects.filter(
            user=self.request.user,
            email=form.instance.email
        ).exclude(pk=self.object.pk).exists():
            messages.error(self.request, 'A contact with this email already exists.')
            return self.form_invalid(form)
        
        contact = form.save()
        
        # Update list counts
        for contact_list in contact.lists.all():
            contact_list.update_contact_count()
        
        messages.success(self.request, f'Contact "{contact.get_full_name()}" updated successfully!')
        return redirect('backend:contact_detail', pk=contact.pk)


@method_decorator(login_required, name='dispatch')
class ContactDeleteView(DeleteView):
    """Delete contact"""
    
    model = Contact
    template_name = 'contacts/contact_delete.html'
    success_url = reverse_lazy('backend:contact_list')
    
    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        contact = self.get_object()
        contact_lists = list(contact.lists.all())
        contact_name = contact.get_full_name()
        
        # Soft delete - mark as inactive instead of actually deleting
        contact.is_active = False
        contact.save()
        
        # Update list counts
        for contact_list in contact_lists:
            contact_list.update_contact_count()
        
        messages.success(request, f'Contact "{contact_name}" deleted successfully!')
        return redirect(self.success_url)


@method_decorator(login_required, name='dispatch')
class ContactImportView(TemplateView):
    """Import contacts from CSV/Excel"""
    
    template_name = 'contacts/contact_import.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ContactImportForm(self.request.user)
        
        # Get recent imports
        context['recent_imports'] = ContactImport.objects.filter(
            user=self.request.user
        ).order_by('-started_at')[:5]
        
        return context
    
    def post(self, request):
        form = ContactImportForm(request.user, request.POST, request.FILES)
        
        if form.is_valid():
            file = form.cleaned_data['csv_file']
            options = {
                'target_list': form.cleaned_data.get('target_list'),
                'skip_duplicates': form.cleaned_data.get('skip_duplicates', True),
                'update_existing': form.cleaned_data.get('update_existing', False),
            }
            
            # Process import
            contact_service = ContactService()
            result = contact_service.import_contacts_from_file(
                user=request.user,
                file=file,
                options=options
            )
            
            if result['success']:
                messages.success(
                    request,
                    f'Import started successfully! '
                    f'{result["result"]["successful"]} contacts imported, '
                    f'{result["result"]["failed"]} failed, '
                    f'{result["result"]["duplicates"]} duplicates skipped.'
                )
                return redirect('backend:contact_import_status', import_id=result['import_id'])
            else:
                messages.error(request, f'Import failed: {result["error"]}')
        
        context = self.get_context_data()
        context['form'] = form
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class ContactImportStatusView(DetailView):
    """View import status"""
    
    model = ContactImport
    template_name = 'contacts/contact_import_status.html'
    context_object_name = 'import_record'
    pk_url_kwarg = 'import_id'
    
    def get_queryset(self):
        return ContactImport.objects.filter(user=self.request.user)


@method_decorator(login_required, name='dispatch')
class ContactExportView(View):
    """Export contacts to CSV/Excel"""
    
    def get(self, request):
        format_type = request.GET.get('format', 'csv')
        contact_list_id = request.GET.get('list_id')
        status_filter = request.GET.get('status')
        
        # Build filter
        contact_filter = {}
        if contact_list_id:
            contact_filter['lists'] = contact_list_id
        if status_filter:
            contact_filter['status'] = status_filter
        
        # Export contacts
        contact_service = ContactService()
        try:
            if format_type == 'csv':
                export_data = contact_service.export_contacts(
                    user=request.user,
                    contact_filter=contact_filter,
                    format='csv'
                )
                
                response = HttpResponse(export_data, content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="contacts_{timezone.now().strftime("%Y%m%d")}.csv"'
                
            else:  # Excel
                export_data = contact_service.export_contacts(
                    user=request.user,
                    contact_filter=contact_filter,
                    format='excel'
                )
                
                response = HttpResponse(
                    export_data,
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="contacts_{timezone.now().strftime("%Y%m%d")}.xlsx"'
            
            return response
            
        except Exception as e:
            logger.error(f"Contact export error: {str(e)}")
            messages.error(request, 'Export failed. Please try again.')
            return redirect('backend:contact_list')


@method_decorator(login_required, name='dispatch')
class ContactBulkActionsView(View):
    """Handle bulk actions on contacts"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            action = data.get('action')
            contact_ids = data.get('contact_ids', [])
            
            if not contact_ids:
                return JsonResponse({'success': False, 'error': 'No contacts selected'})
            
            # Verify contacts belong to user
            contacts = Contact.objects.filter(
                id__in=contact_ids,
                user=request.user
            )
            
            if contacts.count() != len(contact_ids):
                return JsonResponse({'success': False, 'error': 'Some contacts not found'})
            
            if action == 'delete':
                # Soft delete contacts
                contacts.update(is_active=False)
                
                # Update list counts
                for contact in contacts:
                    for contact_list in contact.lists.all():
                        contact_list.update_contact_count()
                
                return JsonResponse({
                    'success': True,
                    'message': f'{contacts.count()} contacts deleted successfully'
                })
            
            elif action == 'add_to_list':
                list_id = data.get('list_id')
                if not list_id:
                    return JsonResponse({'success': False, 'error': 'List ID required'})
                
                contact_list = get_object_or_404(
                    ContactList,
                    id=list_id,
                    user=request.user
                )
                
                # Add contacts to list
                for contact in contacts:
                    contact.lists.add(contact_list)
                
                contact_list.update_contact_count()
                
                return JsonResponse({
                    'success': True,
                    'message': f'{contacts.count()} contacts added to "{contact_list.name}"'
                })
            
            elif action == 'remove_from_list':
                list_id = data.get('list_id')
                if not list_id:
                    return JsonResponse({'success': False, 'error': 'List ID required'})
                
                contact_list = get_object_or_404(
                    ContactList,
                    id=list_id,
                    user=request.user
                )
                
                # Remove contacts from list
                for contact in contacts:
                    contact.lists.remove(contact_list)
                
                contact_list.update_contact_count()
                
                return JsonResponse({
                    'success': True,
                    'message': f'{contacts.count()} contacts removed from "{contact_list.name}"'
                })
            
            elif action == 'add_tag':
                tag_id = data.get('tag_id')
                if not tag_id:
                    return JsonResponse({'success': False, 'error': 'Tag ID required'})
                
                tag = get_object_or_404(
                    ContactTag,
                    id=tag_id,
                    user=request.user
                )
                
                # Add tag to contacts
                for contact in contacts:
                    contact.tags.add(tag)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Tag "{tag.name}" added to {contacts.count()} contacts'
                })
            
            elif action == 'update_status':
                new_status = data.get('status')
                if new_status not in dict(Contact.STATUS_CHOICES):
                    return JsonResponse({'success': False, 'error': 'Invalid status'})
                
                contacts.update(status=new_status)
                
                return JsonResponse({
                    'success': True,
                    'message': f'{contacts.count()} contacts updated to {new_status}'
                })
            
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
        
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Bulk action error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


# Contact List Views
@method_decorator(login_required, name='dispatch')
class ContactListsView(ListView):
    """List contact lists"""
    
    model = ContactList
    template_name = 'contacts/contact_lists.html'
    context_object_name = 'contact_lists'
    paginate_by = 20
    
    def get_queryset(self):
        return ContactList.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-updated_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add summary statistics
        context['stats'] = {
            'total_lists': self.get_queryset().count(),
            'total_contacts_in_lists': sum([lst.contact_count for lst in self.get_queryset()]),
            'favorite_lists': self.get_queryset().filter(is_favorite=True).count(),
        }
        
        return context


@method_decorator(login_required, name='dispatch')
class ContactListCreateView(CreateView):
    """Create contact list"""
    
    model = ContactList
    form_class = ContactListForm
    template_name = 'contacts/contact_list_create.html'
    success_url = reverse_lazy('backend:contact_lists')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, f'List "{form.instance.name}" created successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class ContactListDetailView(DetailView):
    """Contact list detail view"""
    
    model = ContactList
    template_name = 'contacts/contact_list_detail.html'
    context_object_name = 'contact_list'
    
    def get_queryset(self):
        return ContactList.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact_list = self.object
        
        # Get contacts in this list
        contacts = contact_list.contacts.filter(is_active=True).order_by('-created_at')
        
        # Paginate contacts
        paginator = Paginator(contacts, 25)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context['contacts'] = page_obj
        context['is_paginated'] = page_obj.has_other_pages()
        context['page_obj'] = page_obj
        
        # Get list statistics
        context['list_stats'] = {
            'active_contacts': contacts.filter(status='ACTIVE').count(),
            'unsubscribed_contacts': contacts.filter(status='UNSUBSCRIBED').count(),
            'bounced_contacts': contacts.filter(status='BOUNCED').count(),
            'avg_engagement_score': contacts.aggregate(
                avg_score=models.Avg('engagement_score')
            )['avg_score'] or 0,
        }
        
        return context


@method_decorator(login_required, name='dispatch')
class ContactListUpdateView(UpdateView):
    """Update contact list"""
    
    model = ContactList
    form_class = ContactListForm
    template_name = 'contacts/contact_list_update.html'
    
    def get_queryset(self):
        return ContactList.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, f'List "{form.instance.name}" updated successfully!')
        return redirect('backend:contact_list_detail', pk=self.object.pk)


@method_decorator(login_required, name='dispatch')
class ContactListDeleteView(DeleteView):
    """Delete contact list"""
    
    model = ContactList
    template_name = 'contacts/contact_list_delete.html'
    success_url = reverse_lazy('backend:contact_lists')
    
    def get_queryset(self):
        return ContactList.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        contact_list = self.get_object()
        contact_list_name = contact_list.name
        
        # Soft delete - mark as inactive
        contact_list.is_active = False
        contact_list.save()
        
        messages.success(request, f'List "{contact_list_name}" deleted successfully!')
        return redirect(self.success_url)


# AJAX Views
@method_decorator(login_required, name='dispatch')
class ContactCountAjaxView(View):
    """Get contact count for filters via AJAX"""
    
    def get(self, request):
        try:
            list_id = request.GET.get('list_id')
            status = request.GET.get('status')
            
            contacts = Contact.objects.filter(
                user=request.user,
                is_active=True
            )
            
            if list_id:
                contacts = contacts.filter(lists=list_id)
            
            if status:
                contacts = contacts.filter(status=status)
            
            return JsonResponse({
                'success': True,
                'count': contacts.count()
            })
            
        except Exception as e:
            logger.error(f"Contact count error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class QuickAddContactView(View):
    """Quick add contact via AJAX"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            email = data.get('email')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            list_id = data.get('list_id')
            
            if not email:
                return JsonResponse({'success': False, 'error': 'Email is required'})
            
            # Check if contact already exists
            if Contact.objects.filter(user=request.user, email=email).exists():
                return JsonResponse({'success': False, 'error': 'Contact already exists'})
            
            # Create contact
            contact = Contact.objects.create(
                user=request.user,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            
            # Add to list if specified
            if list_id:
                try:
                    contact_list = ContactList.objects.get(
                        id=list_id,
                        user=request.user
                    )
                    contact.lists.add(contact_list)
                    contact_list.update_contact_count()
                except ContactList.DoesNotExist:
                    pass
            
            return JsonResponse({
                'success': True,
                'contact': {
                    'id': str(contact.id),
                    'email': contact.email,
                    'name': contact.get_full_name(),
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Quick add contact error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Server error'})


@method_decorator(login_required, name='dispatch')
class ContactEngagementView(DetailView):
    """View contact engagement details"""
    
    model = Contact
    template_name = 'contacts/contact_engagement.html'
    context_object_name = 'contact'
    
    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self.object
        
        # Get engagement data for the last 30 days
        from datetime import timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Get daily engagement data
        engagement_data = []
        for i in range(30):
            date = (timezone.now() - timedelta(days=i)).date()
            
            events = EmailEvent.objects.filter(
                contact=contact,
                created_at__date=date
            )
            
            engagement_data.append({
                'date': date.isoformat(),
                'opens': events.filter(event_type='OPENED').count(),
                'clicks': events.filter(event_type='CLICKED').count(),
            })
        
        context['engagement_data'] = list(reversed(engagement_data))
        
        # Get email frequency
        context['email_frequency'] = EmailEvent.objects.filter(
            contact=contact,
            event_type='SENT',
            created_at__gte=thirty_days_ago
        ).count()
        
        return context