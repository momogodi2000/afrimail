
# backend/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import CustomUser, UserProfile, Contact, ContactList, EmailEvent, EmailCampaign
from .tasks import send_welcome_email
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile when user is created"""
    if created:
        UserProfile.objects.create(user=instance)
        logger.info(f"Created profile for user: {instance.email}")


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """Save user profile when user is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=CustomUser)
def send_welcome_email_signal(sender, instance, created, **kwargs):
    """Send welcome email to new verified users"""
    if created and instance.is_email_verified and instance.is_active:
        # Send welcome email asynchronously
        send_welcome_email.delay(str(instance.id))
        logger.info(f"Scheduled welcome email for: {instance.email}")


@receiver(post_save, sender=Contact)
def update_contact_list_counts(sender, instance, created, **kwargs):
    """Update contact list counts when contact is saved"""
    if created:
        # Update counts for all lists this contact belongs to
        for contact_list in instance.lists.all():
            contact_list.update_contact_count()


@receiver(post_delete, sender=Contact)
def update_contact_list_counts_on_delete(sender, instance, **kwargs):
    """Update contact list counts when contact is deleted"""
    # Update counts for all lists this contact belonged to
    for contact_list in instance.lists.all():
        contact_list.update_contact_count()


@receiver(post_save, sender=EmailEvent)
def update_contact_engagement(sender, instance, created, **kwargs):
    """Update contact engagement when email events occur"""
    if created:
        contact = instance.contact
        
        if instance.event_type == 'OPENED':
            contact.record_email_opened()
        elif instance.event_type == 'CLICKED':
            contact.record_email_clicked()


@receiver(post_save, sender=EmailEvent)
def update_campaign_metrics(sender, instance, created, **kwargs):
    """Update campaign metrics when email events occur"""
    if created:
        campaign = instance.campaign
        
        # Check if this is a unique event for this contact
        existing_events = EmailEvent.objects.filter(
            campaign=campaign,
            contact=instance.contact,
            event_type=instance.event_type
        ).count()
        
        is_unique = existing_events == 1  # Only one event means it's the first (unique)
        
        if instance.event_type == 'OPENED':
            campaign.record_open(is_unique)
        elif instance.event_type == 'CLICKED':
            campaign.record_click(is_unique)
        elif instance.event_type == 'UNSUBSCRIBED':
            campaign.record_unsubscribe()
        elif instance.event_type == 'BOUNCED':
            campaign.increment_bounced()
        elif instance.event_type == 'DELIVERED':
            campaign.increment_delivered()


@receiver(post_save, sender=EmailCampaign)
def log_campaign_status_change(sender, instance, created, **kwargs):
    """Log campaign status changes"""
    if not created:
        # Check if status changed
        old_instance = EmailCampaign.objects.get(pk=instance.pk)
        if hasattr(old_instance, '_state') and old_instance.status != instance.status:
            logger.info(f"Campaign {instance.name} status changed from {old_instance.status} to {instance.status}")