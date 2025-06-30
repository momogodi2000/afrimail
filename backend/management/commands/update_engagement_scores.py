
# backend/management/commands/update_engagement_scores.py

from django.core.management.base import BaseCommand
from backend.models import Contact, ContactEngagement
from django.utils import timezone


class Command(BaseCommand):
    help = 'Update engagement scores for all contacts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            help='Update scores only for specific user ID'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Process contacts in batches of this size'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('📊 Updating contact engagement scores...')
        
        # Get contacts to process
        contacts = Contact.objects.filter(is_active=True)
        
        if options['user_id']:
            contacts = contacts.filter(user_id=options['user_id'])
        
        total_contacts = contacts.count()
        batch_size = options['batch_size']
        
        self.stdout.write(f'Processing {total_contacts} contacts in batches of {batch_size}...')
        
        updated_count = 0
        
        for i in range(0, total_contacts, batch_size):
            batch = contacts[i:i + batch_size]
            
            for contact in batch:
                old_score = contact.engagement_score
                new_score = contact.calculate_engagement_score()
                
                if abs(old_score - new_score) > 0.1:  # Only save if significant change
                    contact.save(update_fields=['engagement_score'])
                    updated_count += 1
                
                # Create today's engagement record if it doesn't exist
                today = timezone.now().date()
                engagement, created = ContactEngagement.objects.get_or_create(
                    contact=contact,
                    date=today,
                    defaults={
                        'engagement_score': new_score
                    }
                )
                
                if not created:
                    engagement.calculate_engagement_score()
            
            # Progress indicator
            processed = min(i + batch_size, total_contacts)
            progress = (processed / total_contacts) * 100
            self.stdout.write(f'Progress: {progress:.1f}% ({processed}/{total_contacts})')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Updated engagement scores for {updated_count} contacts'
            )
        )

