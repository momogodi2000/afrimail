# backend/services/__init__.py

from .email_service import EmailService
from .campaign_service import CampaignService
from .contact_service import ContactService
from .analytics_service import AnalyticsService

__all__ = ['EmailService', 'CampaignService', 'ContactService', 'AnalyticsService']

