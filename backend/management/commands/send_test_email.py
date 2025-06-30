
# backend/management/commands/send_test_email.py

from django.core.management.base import BaseCommand
from backend.services.email_service import EmailService


class Command(BaseCommand):
    help = 'Send a test email to verify email configuration'
    
    def add_arguments(self, parser):
        parser.add_argument('email', help='Email address to send test email to')
        parser.add_argument('--from-email', help='From email address')
        parser.add_argument('--subject', help='Email subject', default='Test Email from AfriMail Pro')
    
    def handle(self, *args, **options):
        email_service = EmailService()
        
        test_content = f"""
        <h2>🎉 Test Email from AfriMail Pro</h2>
        <p>Congratulations! Your email configuration is working correctly.</p>
        <p><strong>Sent to:</strong> {options['email']}</p>
        <p><strong>Sent at:</strong> {timezone.now()}</p>
        <p>This test confirms that AfriMail Pro can successfully send emails.</p>
        <hr>
        <p><small>AfriMail Pro - Connectez l'Afrique, Un Email à la Fois</small></p>
        """
        
        result = email_service.send_email(
            to_email=options['email'],
            subject=options['subject'],
            html_content=test_content,
            from_email=options.get('from_email'),
            from_name='AfriMail Pro Test'
        )
        
        if result:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Test email sent successfully to {options["email"]}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Failed to send test email to {options["email"]}')
            )

