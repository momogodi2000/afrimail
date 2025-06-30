# backend/api_views.py

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.db.models import Q, Count
import json
import logging

from .models import (
    CustomUser, Contact, ContactList, EmailCampaign, 
    EmailEvent, CampaignAnalytics
)
from .services import ContactService, CampaignService, AnalyticsService

logger = logging.getLogger(__name__)


class APIBaseView(View):
    """Base API view with common functionality"""
    
    def dispatch(self, request, *args, **kwargs):
        """Override to add JSON response handling"""
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"API Error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    def json_response(self, data, status=200):
        """Helper method for JSON responses"""
        return JsonResponse(data, status=status)


# Authentication API Views
@method_decorator(csrf_exempt, name='dispatch')
class APILoginView(APIBaseView):
    """API Login endpoint"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                return self.json_response({
                    'success': False,
                    'error': 'Email and password are required'
                }, status=400)
            
            user = authenticate(request, username=email, password=password)
            
            if user and user.is_active:
                login(request, user)
                return self.json_response({
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'is_super_admin': user.is_super_admin,
                    }
                })
            else:
                return self.json_response({
                    'success': False,
                    'error': 'Invalid credentials'
                }, status=401)
        
        except json.JSONDecodeError:
            return self.json_response({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"API Login error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Login failed'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class APILogoutView(APIBaseView):
    """API Logout endpoint"""
    
    def post(self, request):
        logout(request)
        return self.json_response({
            'success': True,
            'message': 'Logout successful'
        })


@method_decorator(login_required, name='dispatch')
class APIUserView(APIBaseView):
    """API User info endpoint"""
    
    def get(self, request):
        user = request.user
        return self.json_response({
            'success': True,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'company': user.company,
                'is_super_admin': user.is_super_admin,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }
        })


# Contact API Views
@method_decorator(login_required, name='dispatch')
class ContactListAPIView(APIBaseView):
    """API for listing contacts"""
    
    def get(self, request):
        try:
            # Get query parameters
            search = request.GET.get('search', '')
            limit = int(request.GET.get('limit', 25))
            offset = int(request.GET.get('offset', 0))
            
            # Build queryset
            contacts = Contact.objects.filter(
                user=request.user,
                is_active=True
            )
            
            if search:
                contacts = contacts.filter(
                    Q(email__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search)
                )
            
            # Get total count
            total_count = contacts.count()
            
            # Apply pagination
            contacts = contacts[offset:offset + limit]
            
            # Serialize contacts
            contact_data = []
            for contact in contacts:
                contact_data.append({
                    'id': str(contact.id),
                    'email': contact.email,
                    'first_name': contact.first_name,
                    'last_name': contact.last_name,
                    'company': contact.company,
                    'status': contact.status,
                    'created_at': contact.created_at.isoformat(),
                })
            
            return self.json_response({
                'success': True,
                'contacts': contact_data,
                'total_count': total_count,
                'has_next': offset + limit < total_count,
            })
        
        except Exception as e:
            logger.error(f"Contact list API error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Failed to retrieve contacts'
            }, status=500)


@method_decorator(login_required, name='dispatch')
class ContactDetailAPIView(APIBaseView):
    """API for contact details"""
    
    def get(self, request, pk):
        try:
            contact = Contact.objects.get(
                id=pk,
                user=request.user,
                is_active=True
            )
            
            return self.json_response({
                'success': True,
                'contact': {
                    'id': str(contact.id),
                    'email': contact.email,
                    'first_name': contact.first_name,
                    'last_name': contact.last_name,
                    'company': contact.company,
                    'phone': contact.phone,
                    'country': contact.country,
                    'status': contact.status,
                    'created_at': contact.created_at.isoformat(),
                    'updated_at': contact.updated_at.isoformat(),
                }
            })
        
        except Contact.DoesNotExist:
            return self.json_response({
                'success': False,
                'error': 'Contact not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Contact detail API error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Failed to retrieve contact'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class ContactBulkImportAPIView(APIBaseView):
    """API for bulk contact import"""
    
    def post(self, request):
        try:
            if 'file' not in request.FILES:
                return self.json_response({
                    'success': False,
                    'error': 'No file provided'
                }, status=400)
            
            uploaded_file = request.FILES['file']
            
            # Use ContactService for import
            contact_service = ContactService()
            result = contact_service.import_contacts_from_file(
                user=request.user,
                file=uploaded_file
            )
            
            return self.json_response(result)
        
        except Exception as e:
            logger.error(f"Bulk import API error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Import failed'
            }, status=500)


# Campaign API Views
@method_decorator(login_required, name='dispatch')
class CampaignListAPIView(APIBaseView):
    """API for listing campaigns"""
    
    def get(self, request):
        try:
            # Get query parameters
            limit = int(request.GET.get('limit', 25))
            offset = int(request.GET.get('offset', 0))
            status = request.GET.get('status')
            
            # Build queryset
            campaigns = EmailCampaign.objects.filter(user=request.user)
            
            if status:
                campaigns = campaigns.filter(status=status)
            
            # Get total count
            total_count = campaigns.count()
            
            # Apply pagination
            campaigns = campaigns[offset:offset + limit]
            
            # Serialize campaigns
            campaign_data = []
            for campaign in campaigns:
                campaign_data.append({
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'subject': campaign.subject,
                    'status': campaign.status,
                    'campaign_type': campaign.campaign_type,
                    'recipient_count': campaign.recipient_count,
                    'emails_sent': campaign.emails_sent,
                    'created_at': campaign.created_at.isoformat(),
                    'sent_at': campaign.sent_at.isoformat() if campaign.sent_at else None,
                })
            
            return self.json_response({
                'success': True,
                'campaigns': campaign_data,
                'total_count': total_count,
                'has_next': offset + limit < total_count,
            })
        
        except Exception as e:
            logger.error(f"Campaign list API error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Failed to retrieve campaigns'
            }, status=500)


@method_decorator(login_required, name='dispatch')
class CampaignDetailAPIView(APIBaseView):
    """API for campaign details"""
    
    def get(self, request, pk):
        try:
            campaign = EmailCampaign.objects.get(
                id=pk,
                user=request.user
            )
            
            return self.json_response({
                'success': True,
                'campaign': {
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'subject': campaign.subject,
                    'description': campaign.description,
                    'status': campaign.status,
                    'campaign_type': campaign.campaign_type,
                    'recipient_count': campaign.recipient_count,
                    'emails_sent': campaign.emails_sent,
                    'html_content': campaign.html_content,
                    'text_content': campaign.text_content,
                    'created_at': campaign.created_at.isoformat(),
                    'updated_at': campaign.updated_at.isoformat(),
                    'sent_at': campaign.sent_at.isoformat() if campaign.sent_at else None,
                }
            })
        
        except EmailCampaign.DoesNotExist:
            return self.json_response({
                'success': False,
                'error': 'Campaign not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Campaign detail API error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Failed to retrieve campaign'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class CampaignSendAPIView(APIBaseView):
    """API for sending campaigns"""
    
    def post(self, request, pk):
        try:
            campaign = EmailCampaign.objects.get(
                id=pk,
                user=request.user
            )
            
            if campaign.status != 'DRAFT':
                return self.json_response({
                    'success': False,
                    'error': 'Campaign is not in draft status'
                }, status=400)
            
            # Use CampaignService to send campaign
            campaign_service = CampaignService()
            result = campaign_service.send_campaign(campaign)
            
            return self.json_response(result)
        
        except EmailCampaign.DoesNotExist:
            return self.json_response({
                'success': False,
                'error': 'Campaign not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Campaign send API error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Failed to send campaign'
            }, status=500)


@method_decorator(login_required, name='dispatch')
class CampaignAnalyticsAPIView(APIBaseView):
    """API for campaign analytics"""
    
    def get(self, request, pk=None):
        try:
            if pk:
                # Single campaign analytics
                campaign = EmailCampaign.objects.get(
                    id=pk,
                    user=request.user
                )
                
                analytics_service = AnalyticsService()
                analytics = analytics_service.get_campaign_detailed_analytics(campaign)
                
                return self.json_response({
                    'success': True,
                    'analytics': analytics
                })
            else:
                # Overall campaign analytics
                analytics_service = AnalyticsService()
                analytics = analytics_service.get_user_analytics(request.user, days=30)
                
                return self.json_response({
                    'success': True,
                    'analytics': analytics
                })
        
        except EmailCampaign.DoesNotExist:
            return self.json_response({
                'success': False,
                'error': 'Campaign not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Campaign analytics API error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Failed to retrieve analytics'
            }, status=500)


# Analytics API Views
@method_decorator(login_required, name='dispatch')
class AnalyticsOverviewAPIView(APIBaseView):
    """API for analytics overview"""
    
    def get(self, request):
        try:
            days = int(request.GET.get('days', 30))
            
            analytics_service = AnalyticsService()
            analytics = analytics_service.get_user_analytics(request.user, days=days)
            
            return self.json_response({
                'success': True,
                'analytics': analytics
            })
        
        except Exception as e:
            logger.error(f"Analytics overview API error: {str(e)}")
            return self.json_response({
                'success': False,
                'error': 'Failed to retrieve analytics'
            }, status=500)