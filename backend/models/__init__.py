# backend/models/__init__.py

from .user_models import CustomUser, UserProfile, UserActivity
from .contact_models import Contact, ContactList, ContactTag, ContactImport
from .email_models import EmailDomainConfig, EmailTemplate, EmailCampaign, EmailQueue
from .analytics_models import (
    EmailEvent, CampaignAnalytics, ContactEngagement, 
    PlatformAnalytics, ApiUsage, DomainReputation
)

__all__ = [
    # User models
    'CustomUser', 'UserProfile', 'UserActivity',
    
    # Contact models
    'Contact', 'ContactList', 'ContactTag', 'ContactImport',
    
    # Email models
    'EmailDomainConfig', 'EmailTemplate', 'EmailCampaign', 'EmailQueue',
    
    # Analytics models
    'EmailEvent', 'CampaignAnalytics', 'ContactEngagement', 
    'PlatformAnalytics', 'ApiUsage', 'DomainReputation'
]