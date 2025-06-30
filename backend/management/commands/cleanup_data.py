
# backend/management/commands/cleanup_data.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from backend.models import EmailEvent, UserActivity, ApiUsage, ContactImport


class Command(BaseCommand):
    help = 'Clean up old data to keep database size manageable'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Delete data older than this many days (default: 365)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
    
    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=options['days'])
        
        self.stdout.write(f'🧹 Cleaning up data older than {cutoff_date}...')
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will be deleted')
            )
        
        # Clean up email events
        old_events = EmailEvent.objects.filter(created_at__lt=cutoff_date)
        event_count = old_events.count()
        
        if event_count > 0:
            if not options['dry_run']:
                old_events.delete()
            self.stdout.write(f'📧 {"Would delete" if options["dry_run"] else "Deleted"} {event_count} old email events')
        
        # Clean up user activities
        old_activities = UserActivity.objects.filter(created_at__lt=cutoff_date)
        activity_count = old_activities.count()
        
        if activity_count > 0:
            if not options['dry_run']:
                old_activities.delete()
            self.stdout.write(f'👤 {"Would delete" if options["dry_run"] else "Deleted"} {activity_count} old user activities')
        
        # Clean up API usage logs
        old_api_usage = ApiUsage.objects.filter(created_at__lt=cutoff_date)
        api_count = old_api_usage.count()
        
        if api_count > 0:
            if not options['dry_run']:
                old_api_usage.delete()
            self.stdout.write(f'🔗 {"Would delete" if options["dry_run"] else "Deleted"} {api_count} old API usage logs')
        
        # Clean up completed contact imports
        old_imports = ContactImport.objects.filter(
            completed_at__lt=cutoff_date,
            status__in=['COMPLETED', 'FAILED']
        )
        import_count = old_imports.count()
        
        if import_count > 0:
            if not options['dry_run']:
                old_imports.delete()
            self.stdout.write(f'📥 {"Would delete" if options["dry_run"] else "Deleted"} {import_count} old contact imports')
        
        total_cleaned = event_count + activity_count + api_count + import_count
        
        if total_cleaned == 0:
            self.stdout.write(
                self.style.SUCCESS('✨ No old data found to clean up')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ {"Would clean" if options["dry_run"] else "Cleaned"} {total_cleaned} total records'
                )
            )

