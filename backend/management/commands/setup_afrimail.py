# backend/management/__init__.py
# Empty file to make this a Python package


# backend/management/commands/__init__.py
# Empty file to make this a Python package


# backend/management/commands/setup_afrimail.py

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from backend.models import CustomUser, UserProfile, ContactList, ContactTag
from backend.authentication import AuthenticationService
import sys


class Command(BaseCommand):
    help = 'Setup AfriMail Pro with default users and initial data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-users',
            action='store_true',
            help='Skip creating default users',
        )
        parser.add_argument(
            '--skip-data',
            action='store_true',
            help='Skip creating sample data',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            help='Email for the super admin user',
            default='admin@afrimailpro.com'
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            help='Password for the super admin user',
            default='SuperAdmin123!'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Setting up AfriMail Pro...')
        )
        
        try:
            with transaction.atomic():
                if not options['skip_users']:
                    self._create_default_users(options)
                
                if not options['skip_data']:
                    self._create_sample_data()
                
                self._create_platform_settings()
                
            self.stdout.write(
                self.style.SUCCESS('✅ AfriMail Pro setup completed successfully!')
            )
            self._display_login_info(options)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Setup failed: {str(e)}')
            )
            raise CommandError(f'Setup failed: {str(e)}')
    
    def _create_default_users(self, options):
        """Create default super admin and client users"""
        self.stdout.write('👤 Creating default users...')
        
        auth_service = AuthenticationService()
        
        # Create Super Admin 1 (Momo Godi Yvan - Platform Owner)
        if not CustomUser.objects.filter(email=options['admin_email']).exists():
            admin_data = {
                'email': options['admin_email'],
                'first_name': 'Momo Godi',
                'last_name': 'Yvan',
                'company': 'AfriMail Pro',
                'password': options['admin_password'],
                'phone': '+237691234567',
                'country': 'CM',
                'city': 'Douala',
                'industry': 'TECHNOLOGY',
                'company_size': '1-5',
                'company_website': 'https://afrimailpro.com',
            }
            
            result = auth_service.create_super_admin(admin_data)
            if result['success']:
                admin = result['user']
                admin.set_password(admin_data['password'])
                admin.save()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Super Admin created: {admin.email}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to create Super Admin: {result["error"]}')
                )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Super Admin already exists: {options["admin_email"]}')
            )
        
        # Create Super Admin 2 (Technical Co-Admin)
        admin2_email = 'tech@afrimailpro.com'
        if not CustomUser.objects.filter(email=admin2_email).exists():
            admin2_data = {
                'email': admin2_email,
                'first_name': 'Technical',
                'last_name': 'Administrator',
                'company': 'AfriMail Pro',
                'password': 'TechAdmin123!',
                'phone': '+237691234568',
                'country': 'CM',
                'city': 'Yaoundé',
                'industry': 'TECHNOLOGY',
                'company_size': '1-5',
            }
            
            result = auth_service.create_super_admin(admin2_data)
            if result['success']:
                admin2 = result['user']
                admin2.set_password(admin2_data['password'])
                admin2.save()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Technical Admin created: {admin2.email}')
                )
        
        # Create Client Users for testing
        client_users = [
            {
                'email': 'marketing@techstartup.cm',
                'first_name': 'Marie',
                'last_name': 'Kouam',
                'company': 'TechStartup Cameroon',
                'password': 'ClientUser123!',
                'phone': '+237698765432',
                'country': 'CM',
                'city': 'Douala',
                'industry': 'TECHNOLOGY',
                'company_size': '6-25',
                'company_website': 'https://techstartup.cm',
            },
            {
                'email': 'contact@ngoeducation.org',
                'first_name': 'Jean',
                'last_name': 'Mballa',
                'company': 'Education For All NGO',
                'password': 'ClientUser123!',
                'phone': '+237677889900',
                'country': 'CM',
                'city': 'Yaoundé',
                'industry': 'EDUCATION',
                'company_size': '26-100',
            },
            {
                'email': 'sales@retailcompany.com',
                'first_name': 'Fatima',
                'last_name': 'Bello',
                'company': 'West Africa Retail Co.',
                'password': 'ClientUser123!',
                'phone': '+234801234567',
                'country': 'NG',
                'city': 'Lagos',
                'industry': 'RETAIL',
                'company_size': '101-500',
            }
        ]
        
        for client_data in client_users:
            if not CustomUser.objects.filter(email=client_data['email']).exists():
                result = auth_service.register_user(client_data)
                if result['success']:
                    user = result['user']
                    # Auto-verify for testing
                    user.verify_email()
                    user.is_active = True
                    user.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Client user created: {user.email}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS('👥 Default users created successfully!')
        )
    
    def _create_sample_data(self):
        """Create sample data for testing"""
        self.stdout.write('📊 Creating sample data...')
        
        # Get a client user to create sample data for
        client_user = CustomUser.objects.filter(role='CLIENT').first()
        if not client_user:
            self.stdout.write(
                self.style.WARNING('⚠️  No client user found, skipping sample data creation')
            )
            return
        
        # Create sample contact lists
        sample_lists = [
            {
                'name': 'Newsletter Subscribers',
                'description': 'General newsletter subscribers',
                'list_type': 'MANUAL'
            },
            {
                'name': 'Premium Customers',
                'description': 'High-value customers',
                'list_type': 'MANUAL'
            },
            {
                'name': 'Event Attendees',
                'description': 'People who attended our events',
                'list_type': 'MANUAL'
            }
        ]
        
        for list_data in sample_lists:
            contact_list, created = ContactList.objects.get_or_create(
                user=client_user,
                name=list_data['name'],
                defaults=list_data
            )
            if created:
                self.stdout.write(f'📋 Created contact list: {contact_list.name}')
        
        # Create sample contact tags
        sample_tags = [
            {'name': 'VIP', 'color': '#FFD700', 'description': 'VIP customers'},
            {'name': 'Lead', 'color': '#32CD32', 'description': 'Potential customers'},
            {'name': 'Active', 'color': '#1E90FF', 'description': 'Active subscribers'},
            {'name': 'Inactive', 'color': '#DC143C', 'description': 'Inactive subscribers'},
        ]
        
        for tag_data in sample_tags:
            tag, created = ContactTag.objects.get_or_create(
                user=client_user,
                name=tag_data['name'],
                defaults=tag_data
            )
            if created:
                self.stdout.write(f'🏷️  Created contact tag: {tag.name}')
        
        self.stdout.write(
            self.style.SUCCESS('📊 Sample data created successfully!')
        )
    
    def _create_platform_settings(self):
        """Create platform-wide settings"""
        self.stdout.write('⚙️  Creating platform settings...')
        
        from django.core.cache import cache
        
        # Set default platform settings
        platform_settings = {
            'platform_name': 'AfriMail Pro',
            'platform_tagline': 'Connectez l\'Afrique, Un Email à la Fois',
            'platform_version': '1.0.0',
            'support_email': 'support@afrimailpro.com',
            'max_contacts_default': 10000,
            'max_campaigns_default': 100,
            'max_emails_default': 50000,
            'email_verification_required': True,
            'maintenance_mode': False,
        }
        
        for key, value in platform_settings.items():
            cache.set(f'platform_{key}', value, 86400 * 30)  # 30 days
        
        self.stdout.write(
            self.style.SUCCESS('⚙️  Platform settings configured!')
        )
    
    def _display_login_info(self, options):
        """Display login information"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS('🎉 AfriMail Pro is ready to use!')
        )
        self.stdout.write('='*60)
        self.stdout.write('\n📧 LOGIN CREDENTIALS:\n')
        
        # Super Admin credentials
        self.stdout.write(
            self.style.HTTP_INFO('👑 SUPER ADMIN ACCESS:')
        )
        self.stdout.write(f'   Email: {options["admin_email"]}')
        self.stdout.write(f'   Password: {options["admin_password"]}')
        self.stdout.write(f'   Dashboard: /admin-panel/')
        
        # Technical Admin credentials
        self.stdout.write(
            self.style.HTTP_INFO('\n🔧 TECHNICAL ADMIN ACCESS:')
        )
        self.stdout.write('   Email: tech@afrimailpro.com')
        self.stdout.write('   Password: TechAdmin123!')
        
        # Client user credentials
        self.stdout.write(
            self.style.HTTP_INFO('\n👤 SAMPLE CLIENT USERS:')
        )
        client_credentials = [
            'marketing@techstartup.cm - ClientUser123!',
            'contact@ngoeducation.org - ClientUser123!',
            'sales@retailcompany.com - ClientUser123!'
        ]
        for cred in client_credentials:
            self.stdout.write(f'   {cred}')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS('🌍 Ready to connect Africa, one email at a time!')
        )
        self.stdout.write('='*60 + '\n')
