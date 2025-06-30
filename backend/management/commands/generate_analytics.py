
# backend/management/commands/generate_analytics.py

from django.core.management.base import BaseCommand
from backend.models import PlatformAnalytics, CampaignAnalytics
from django.utils import timezone


class Command(BaseCommand):
    help = 'Generate and update analytics data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Generate analytics for the last N days'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('📈 Generating analytics data...')
        
        days = options['days']
        
        for i in range(days):
            date = timezone.now().date() - timezone.timedelta(days=i)
            
            # Update platform analytics
            platform_stats = PlatformAnalytics.update_today_stats()
            if i == 0:  # Only update today's stats
                self.stdout.write(f'📊 Updated platform analytics for {date}')
            
            # Update campaign analytics for campaigns that had activity on this date
            from backend.models import EmailCampaign, EmailEvent
            
            campaigns_with_activity = EmailCampaign.objects.filter(
                events__created_at__date=date
            ).distinct()
            
            for campaign in campaigns_with_activity:
                analytics, created = CampaignAnalytics.objects.get_or_create(
                    campaign=campaign,
                    date=date
                )
                
                # Get events for this campaign on this date
                events = EmailEvent.objects.filter(
                    campaign=campaign,
                    created_at__date=date
                )
                
                # Count events by type
                analytics.emails_sent = events.filter(event_type='SENT').count()
                analytics.emails_delivered = events.filter(event_type='DELIVERED').count()
                analytics.unique_opens = events.filter(event_type='OPENED').values('contact').distinct().count()
                analytics.total_opens = events.filter(event_type='OPENED').count()
                analytics.unique_clicks = events.filter(event_type='CLICKED').values('contact').distinct().count()
                analytics.total_clicks = events.filter(event_type='CLICKED').count()
                analytics.emails_bounced = events.filter(event_type='BOUNCED').count()
                analytics.unsubscribes = events.filter(event_type='UNSUBSCRIBED').count()
                
                # Calculate rates
                analytics.calculate_rates()
                
                if created:
                    self.stdout.write(f'📈 Created analytics for campaign: {campaign.name} ({date})')
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Analytics generated for the last {days} days')
        )