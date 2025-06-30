

# backend/management/commands/create_superuser.py

from django.core.management.base import BaseCommand
from django.core.management import CommandError
from backend.authentication import AuthenticationService
import getpass


class Command(BaseCommand):
    help = 'Create a super administrator user for AfriMail Pro'
    
    def add_arguments(self, parser):
        parser.add_argument('--email', help='Email for the super admin')
        parser.add_argument('--first-name', help='First name')
        parser.add_argument('--last-name', help='Last name')
        parser.add_argument('--company', help='Company name', default='AfriMail Pro')
        parser.add_argument('--no-input', action='store_true', help='Skip interactive input')
    
    def handle(self, *args, **options):
        if options['no_input']:
            if not all([options.get('email'), options.get('first_name'), options.get('last_name')]):
                raise CommandError('--email, --first-name, and --last-name are required when using --no-input')
        
        email = options.get('email') or input('Email: ')
        first_name = options.get('first_name') or input('First name: ')
        last_name = options.get('last_name') or input('Last name: ')
        company = options.get('company') or input('Company (default: AfriMail Pro): ') or 'AfriMail Pro'
        
        while True:
            password = getpass.getpass('Password: ')
            password2 = getpass.getpass('Password (again): ')
            if password == password2:
                break
            self.stdout.write('Passwords do not match. Please try again.')
        
        auth_service = AuthenticationService()
        
        user_data = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'company': company,
            'password': password,
        }
        
        result = auth_service.create_super_admin(user_data)
        
        if result['success']:
            user = result['user']
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Super admin created successfully: {user.email}')
            )
        else:
            raise CommandError(f'Failed to create super admin: {result["error"]}')

