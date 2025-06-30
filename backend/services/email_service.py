
# backend/services/email_service.py

import yagmail
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.core.cache import cache
from ..models import EmailDomainConfig, EmailEvent, EmailQueue
import logging
import re
import base64
import hashlib
from datetime import timedelta
import threading
import time

logger = logging.getLogger(__name__)


class EmailService:
    """
    Comprehensive email service with multiple provider support and yagmail integration
    """
    
    def __init__(self):
        self.yag_cache = {}  # Cache yagmail instances
    
    def get_yagmail_instance(self, email_config=None):
        """Get or create yagmail instance for given configuration"""
        try:
            if email_config is None:
                # Use platform default
                cache_key = 'platform_default'
                if cache_key not in self.yag_cache:
                    self.yag_cache[cache_key] = yagmail.SMTP(
                        user=settings.EMAIL_HOST_USER,
                        password=settings.EMAIL_HOST_PASSWORD,
                        host=settings.EMAIL_HOST or 'smtp.gmail.com',
                        port=settings.EMAIL_PORT or 587,
                        smtp_starttls=True
                    )
                return self.yag_cache[cache_key]
            
            # Use custom email configuration
            cache_key = f"config_{email_config.id}"
            if cache_key not in self.yag_cache:
                if email_config.smtp_provider == 'YAGMAIL' or email_config.smtp_provider == 'GMAIL':
                    self.yag_cache[cache_key] = yagmail.SMTP(
                        user=email_config.smtp_username,
                        password=self._decrypt_password(email_config.smtp_password),
                        host=email_config.smtp_host or 'smtp.gmail.com',
                        port=email_config.smtp_port,
                        smtp_starttls=email_config.use_tls,
                        smtp_ssl=email_config.use_ssl
                    )
                else:
                    # For other providers, we'll use standard SMTP
                    return None
            
            return self.yag_cache[cache_key]
            
        except Exception as e:
            logger.error(f"Error creating yagmail instance: {str(e)}")
            return None
    
    def send_email(self, to_email, subject, html_content, text_content=None, 
                   from_email=None, from_name=None, email_config=None, 
                   attachments=None, campaign=None, contact=None):
        """
        Send email using appropriate provider
        """
        try:
            # Determine email configuration
            if email_config is None and from_email:
                # Try to find email config by from_email
                try:
                    email_config = EmailDomainConfig.objects.get(
                        from_email=from_email,
                        is_active=True,
                        domain_verified=True
                    )
                except EmailDomainConfig.DoesNotExist:
                    pass
            
            # Check rate limits
            if email_config and not email_config.can_send_email():
                logger.warning(f"Rate limit exceeded for domain {email_config.domain_name}")
                return False
            
            # Use yagmail for Gmail/G Suite or platform emails
            if (email_config and email_config.smtp_provider in ['YAGMAIL', 'GMAIL']) or email_config is None:
                result = self._send_with_yagmail(
                    to_email, subject, html_content, text_content,
                    from_email, from_name, email_config, attachments
                )
            else:
                # Use standard SMTP for other providers
                result = self._send_with_smtp(
                    to_email, subject, html_content, text_content,
                    from_email, from_name, email_config, attachments
                )
            
            # Log email event and update usage
            if result:
                if campaign and contact:
                    EmailEvent.log_event(
                        campaign=campaign,
                        contact=contact,
                        event_type='SENT'
                    )
                
                if email_config:
                    email_config.increment_usage()
                
                logger.info(f"Email sent successfully to {to_email}")
            
            return result
            
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
            
            # Log failed event
            if campaign and contact:
                EmailEvent.log_event(
                    campaign=campaign,
                    contact=contact,
                    event_type='FAILED',
                    event_data={'error': str(e)}
                )
            
            return False
    
    def _send_with_yagmail(self, to_email, subject, html_content, text_content=None,
                          from_email=None, from_name=None, email_config=None, attachments=None):
        """Send email using yagmail"""
        try:
            yag = self.get_yagmail_instance(email_config)
            if yag is None:
                return False
            
            # Prepare content
            if text_content is None:
                text_content = strip_tags(html_content)
            
            # Prepare sender
            sender = from_email or settings.DEFAULT_FROM_EMAIL
            if from_name:
                sender = f"{from_name} <{sender}>"
            
            # Send email
            yag.send(
                to=to_email,
                subject=subject,
                contents=[text_content, html_content],
                attachments=attachments or [],
                headers={'From': sender} if from_name else None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Yagmail sending error: {str(e)}")
            return False
    
    def _send_with_smtp(self, to_email, subject, html_content, text_content=None,
                       from_email=None, from_name=None, email_config=None, attachments=None):
        """Send email using standard SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{from_email}>" if from_name else from_email
            msg['To'] = to_email
            
            # Add text content
            if text_content is None:
                text_content = strip_tags(html_content)
            
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    self._add_attachment(msg, attachment)
            
            # Send email
            if email_config:
                smtp_server = email_config.smtp_host
                smtp_port = email_config.smtp_port
                username = email_config.smtp_username
                password = self._decrypt_password(email_config.smtp_password)
                use_tls = email_config.use_tls
                use_ssl = email_config.use_ssl
            else:
                smtp_server = settings.EMAIL_HOST
                smtp_port = settings.EMAIL_PORT
                username = settings.EMAIL_HOST_USER
                password = settings.EMAIL_HOST_PASSWORD
                use_tls = settings.EMAIL_USE_TLS
                use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
            
            # Create SMTP connection
            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port)
                if use_tls:
                    server.starttls()
            
            # Login and send
            server.login(username, password)
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            logger.error(f"SMTP sending error: {str(e)}")
            return False
    
    def _add_attachment(self, msg, attachment_path):
        """Add attachment to email message"""
        try:
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment_path.split("/")[-1]}'
            )
            msg.attach(part)
            
        except Exception as e:
            logger.error(f"Error adding attachment: {str(e)}")
    
    def send_transactional_email(self, to_email, subject, template_name, context=None):
        """Send transactional email using template"""
        try:
            # Render email template
            html_content = render_to_string(f'emails/{template_name}', context or {})
            text_content = render_to_string(
                f'emails/{template_name.replace(".html", ".txt")}', 
                context or {}
            )
            
            return self.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                from_name=settings.PLATFORM_NAME
            )
            
        except Exception as e:
            logger.error(f"Transactional email error: {str(e)}")
            return False
    
    def send_bulk_campaign(self, campaign):
        """Send bulk email campaign"""
        try:
            # Get all active contacts from campaign lists
            contacts = set()
            for contact_list in campaign.contact_lists.all():
                list_contacts = contact_list.contacts.filter(
                    is_active=True,
                    status='ACTIVE'
                ).exclude(
                    email__in=[c.email for c in contacts]  # Avoid duplicates
                )
                contacts.update(list_contacts)
            
            # Update recipient count
            campaign.recipient_count = len(contacts)
            campaign.save(update_fields=['recipient_count'])
            
            # Queue emails for sending
            for contact in contacts:
                self._queue_campaign_email(campaign, contact)
            
            # Start campaign
            campaign.start_sending()
            
            # Process queue in background
            threading.Thread(
                target=self._process_campaign_queue,
                args=(campaign,),
                daemon=True
            ).start()
            
            return True
            
        except Exception as e:
            logger.error(f"Bulk campaign error: {str(e)}")
            campaign.status = 'FAILED'
            campaign.save(update_fields=['status'])
            return False
    
    def _queue_campaign_email(self, campaign, contact):
        """Queue individual campaign email"""
        try:
            # Personalize content
            personalized_subject = self._personalize_content(campaign.subject, contact)
            personalized_html = self._personalize_content(campaign.html_content, contact)
            personalized_text = None
            if campaign.text_content:
                personalized_text = self._personalize_content(campaign.text_content, contact)
            
            # Add tracking pixels and links
            if campaign.track_opens:
                personalized_html = self._add_tracking_pixel(personalized_html, campaign, contact)
            
            if campaign.track_clicks:
                personalized_html = self._add_click_tracking(personalized_html, campaign, contact)
            
            # Create queue entry
            EmailQueue.objects.create(
                campaign=campaign,
                contact=contact,
                personalized_subject=personalized_subject,
                personalized_html_content=personalized_html,
                personalized_text_content=personalized_text
            )
            
        except Exception as e:
            logger.error(f"Queue email error: {str(e)}")
    
    def _process_campaign_queue(self, campaign):
        """Process campaign email queue"""
        try:
            while True:
                # Get pending emails
                pending_emails = EmailQueue.objects.filter(
                    campaign=campaign,
                    status='PENDING',
                    scheduled_at__lte=timezone.now()
                ).order_by('priority', 'scheduled_at')[:10]  # Process 10 at a time
                
                if not pending_emails.exists():
                    # Check if campaign is complete
                    if not EmailQueue.objects.filter(
                        campaign=campaign,
                        status__in=['PENDING', 'RETRYING']
                    ).exists():
                        campaign.complete_sending()
                    break
                
                for queued_email in pending_emails:
                    self._send_queued_email(queued_email)
                    time.sleep(0.1)  # Small delay to avoid overwhelming SMTP
                
                time.sleep(1)  # Wait before next batch
                
        except Exception as e:
            logger.error(f"Campaign queue processing error: {str(e)}")
    
    def _send_queued_email(self, queued_email):
        """Send individual queued email"""
        try:
            campaign = queued_email.campaign
            contact = queued_email.contact
            
            # Send email
            result = self.send_email(
                to_email=contact.email,
                subject=queued_email.personalized_subject,
                html_content=queued_email.personalized_html_content,
                text_content=queued_email.personalized_text_content,
                from_email=campaign.from_email,
                from_name=campaign.from_name,
                email_config=campaign.email_config,
                campaign=campaign,
                contact=contact
            )
            
            if result:
                queued_email.mark_sent()
                campaign.increment_sent()
                contact.record_email_sent()
            else:
                queued_email.mark_failed("Failed to send email")
                campaign.increment_failed()
            
        except Exception as e:
            logger.error(f"Send queued email error: {str(e)}")
            queued_email.mark_failed(str(e))
    
    def _personalize_content(self, content, contact):
        """Personalize email content with contact data"""
        try:
            # Basic personalizations
            personalizations = {
                '{{first_name}}': contact.first_name or contact.get_short_name(),
                '{{last_name}}': contact.last_name or '',
                '{{full_name}}': contact.get_full_name(),
                '{{email}}': contact.email,
                '{{company}}': contact.company or '',
                '{{city}}': contact.city or '',
                '{{country}}': contact.country or '',
            }
            
            # Custom fields
            for field_name, field_value in contact.custom_fields.items():
                personalizations[f'{{{{{field_name}}}}}'] = str(field_value)
            
            # Apply personalizations
            for placeholder, value in personalizations.items():
                content = content.replace(placeholder, value)
            
            return content
            
        except Exception as e:
            logger.error(f"Content personalization error: {str(e)}")
            return content
    
    def _add_tracking_pixel(self, html_content, campaign, contact):
        """Add tracking pixel for open tracking"""
        try:
            # Generate tracking token
            tracking_data = f"{campaign.id}:{contact.id}:{timezone.now().timestamp()}"
            tracking_token = base64.urlsafe_b64encode(tracking_data.encode()).decode()
            
            # Create tracking pixel
            tracking_pixel = f'<img src="http://localhost:8000/track/open/{tracking_token}/" width="1" height="1" style="display:none;" />'
            
            # Add to end of HTML content
            if '</body>' in html_content:
                html_content = html_content.replace('</body>', f'{tracking_pixel}</body>')
            else:
                html_content += tracking_pixel
            
            return html_content
            
        except Exception as e:
            logger.error(f"Add tracking pixel error: {str(e)}")
            return html_content
    
    def _add_click_tracking(self, html_content, campaign, contact):
        """Add click tracking to links"""
        try:
            # Find all links
            link_pattern = r'<a\s+href="([^"]+)"([^>]*)>(.*?)</a>'
            
            def replace_link(match):
                url = match.group(1)
                attributes = match.group(2)
                text = match.group(3)
                
                # Skip unsubscribe and tracking links
                if 'unsubscribe' in url.lower() or 'track/' in url:
                    return match.group(0)
                
                # Generate tracking URL
                tracking_data = f"{campaign.id}:{contact.id}:{url}"
                tracking_token = base64.urlsafe_b64encode(tracking_data.encode()).decode()
                tracking_url = f"http://localhost:8000/track/click/{tracking_token}/"
                
                return f'<a href="{tracking_url}"{attributes}>{text}</a>'
            
            return re.sub(link_pattern, replace_link, html_content, flags=re.IGNORECASE | re.DOTALL)
            
        except Exception as e:
            logger.error(f"Add click tracking error: {str(e)}")
            return html_content
    
    def test_email_configuration(self, email_config):
        """Test email configuration"""
        try:
            test_subject = f"Test Email from {settings.PLATFORM_NAME}"
            test_content = f"""
            <h2>Email Configuration Test</h2>
            <p>This is a test email to verify your email configuration.</p>
            <p><strong>Domain:</strong> {email_config.domain_name}</p>
            <p><strong>From Email:</strong> {email_config.from_email}</p>
            <p><strong>SMTP Provider:</strong> {email_config.get_smtp_provider_display()}</p>
            <p>If you received this email, your configuration is working correctly!</p>
            """
            
            return self.send_email(
                to_email=email_config.from_email,
                subject=test_subject,
                html_content=test_content,
                from_email=email_config.from_email,
                from_name=email_config.from_name,
                email_config=email_config
            )
            
        except Exception as e:
            logger.error(f"Test email configuration error: {str(e)}")
            return False
    
    def _encrypt_password(self, password):
        """Encrypt password for storage"""
        try:
            # Simple base64 encoding (use proper encryption in production)
            return base64.b64encode(password.encode()).decode()
        except:
            return password
    
    def _decrypt_password(self, encrypted_password):
        """Decrypt password from storage"""
        try:
            # Simple base64 decoding (use proper decryption in production)
            return base64.b64decode(encrypted_password.encode()).decode()
        except:
            return encrypted_password
    
    def get_delivery_statistics(self, days=30):
        """Get email delivery statistics"""
        try:
            from django.db.models import Count
            from datetime import timedelta
            
            start_date = timezone.now() - timedelta(days=days)
            
            stats = EmailEvent.objects.filter(
                created_at__gte=start_date
            ).values('event_type').annotate(
                count=Count('id')
            )
            
            result = {
                'sent': 0,
                'delivered': 0,
                'opened': 0,
                'clicked': 0,
                'bounced': 0,
                'failed': 0,
            }
            
            for stat in stats:
                event_type = stat['event_type'].lower()
                if event_type in result:
                    result[event_type] = stat['count']
            
            # Calculate rates
            if result['sent'] > 0:
                result['delivery_rate'] = (result['delivered'] / result['sent']) * 100
                result['bounce_rate'] = (result['bounced'] / result['sent']) * 100
            
            if result['delivered'] > 0:
                result['open_rate'] = (result['opened'] / result['delivered']) * 100
                result['click_rate'] = (result['clicked'] / result['delivered']) * 100
            
            return result
            
        except Exception as e:
            logger.error(f"Get delivery statistics error: {str(e)}")
            return {}