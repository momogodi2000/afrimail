
# backend/services/contact_service.py

import csv
import io
import pandas as pd
from django.db import transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from ..models import Contact, ContactList, ContactTag, ContactImport
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ContactService:
    """Service for managing contacts"""
    
    def create_contact(self, user, contact_data):
        """Create a new contact"""
        try:
            with transaction.atomic():
                # Check for duplicates
                if Contact.objects.filter(user=user, email=contact_data['email']).exists():
                    return {'success': False, 'error': 'Contact with this email already exists'}
                
                contact = Contact.objects.create(user=user, **contact_data)
                
                # Update contact lists counts
                for contact_list in contact.lists.all():
                    contact_list.update_contact_count()
                
                logger.info(f"Contact created: {contact.email} by {user.email}")
                return {'success': True, 'contact': contact}
                
        except Exception as e:
            logger.error(f"Contact creation error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def update_contact(self, contact, contact_data):
        """Update an existing contact"""
        try:
            with transaction.atomic():
                old_lists = set(contact.lists.all())
                
                # Update contact fields
                for field, value in contact_data.items():
                    if hasattr(contact, field):
                        setattr(contact, field, value)
                
                contact.save()
                
                # Update list counts if lists changed
                new_lists = set(contact.lists.all())
                changed_lists = old_lists.union(new_lists)
                
                for contact_list in changed_lists:
                    contact_list.update_contact_count()
                
                logger.info(f"Contact updated: {contact.email}")
                return {'success': True, 'contact': contact}
                
        except Exception as e:
            logger.error(f"Contact update error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def delete_contact(self, contact):
        """Delete a contact"""
        try:
            with transaction.atomic():
                contact_lists = list(contact.lists.all())
                email = contact.email
                
                contact.delete()
                
                # Update list counts
                for contact_list in contact_lists:
                    contact_list.update_contact_count()
                
                logger.info(f"Contact deleted: {email}")
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Contact deletion error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def import_contacts_from_file(self, user, file, options=None):
        """Import contacts from CSV/Excel file"""
        options = options or {}
        skip_duplicates = options.get('skip_duplicates', True)
        update_existing = options.get('update_existing', False)
        target_list = options.get('target_list')
        
        try:
            # Create import record
            import_record = ContactImport.objects.create(
                user=user,
                file_name=file.name,
                file_path=f"imports/{file.name}",
                target_list=target_list
            )
            
            # Process file
            try:
                contacts_data = self._parse_contact_file(file)
                import_record.total_rows = len(contacts_data)
                import_record.save()
                
                # Process contacts
                result = self._process_contact_import(
                    user, contacts_data, import_record, options
                )
                
                import_record.mark_completed()
                
                logger.info(f"Contact import completed: {result['successful']} successful, {result['failed']} failed")
                return {
                    'success': True,
                    'import_id': import_record.id,
                    'result': result
                }
                
            except Exception as e:
                import_record.mark_failed(str(e))
                raise e
                
        except Exception as e:
            logger.error(f"Contact import error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _parse_contact_file(self, file):
        """Parse contact file (CSV or Excel)"""
        file_extension = file.name.lower().split('.')[-1]
        
        if file_extension == 'csv':
            return self._parse_csv_file(file)
        elif file_extension in ['xlsx', 'xls']:
            return self._parse_excel_file(file)
        else:
            raise ValueError('Unsupported file format')
    
    def _parse_csv_file(self, file):
        """Parse CSV file"""
        try:
            # Read file content
            file_content = file.read().decode('utf-8')
            file.seek(0)  # Reset file pointer
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(file_content))
            contacts_data = []
            
            for row in csv_reader:
                # Clean and normalize field names
                cleaned_row = {}
                for key, value in row.items():
                    if key:
                        clean_key = key.strip().lower().replace(' ', '_')
                        cleaned_row[clean_key] = value.strip() if value else ''
                
                contacts_data.append(cleaned_row)
            
            return contacts_data
            
        except Exception as e:
            raise ValueError(f'Error parsing CSV file: {str(e)}')
    
    def _parse_excel_file(self, file):
        """Parse Excel file"""
        try:
            # Read Excel file
            df = pd.read_excel(file)
            
            # Convert to list of dictionaries
            contacts_data = []
            for _, row in df.iterrows():
                cleaned_row = {}
                for key, value in row.items():
                    if pd.notna(key):
                        clean_key = str(key).strip().lower().replace(' ', '_')
                        cleaned_row[clean_key] = str(value).strip() if pd.notna(value) else ''
                
                contacts_data.append(cleaned_row)
            
            return contacts_data
            
        except Exception as e:
            raise ValueError(f'Error parsing Excel file: {str(e)}')
    
    def _process_contact_import(self, user, contacts_data, import_record, options):
        """Process contact import data"""
        successful = 0
        failed = 0
        duplicates = 0
        
        # Field mapping
        field_mapping = {
            'email': ['email', 'email_address', 'e_mail'],
            'first_name': ['first_name', 'firstname', 'fname', 'given_name'],
            'last_name': ['last_name', 'lastname', 'lname', 'surname', 'family_name'],
            'phone': ['phone', 'phone_number', 'mobile', 'telephone'],
            'company': ['company', 'organization', 'org', 'business'],
            'job_title': ['job_title', 'title', 'position', 'role'],
            'city': ['city', 'town'],
            'country': ['country', 'nation'],
            'website': ['website', 'url', 'web_site'],
        }
        
        for row_num, row_data in enumerate(contacts_data, start=1):
            try:
                # Map fields
                contact_data = self._map_contact_fields(row_data, field_mapping)
                
                # Validate email
                if not contact_data.get('email'):
                    import_record.add_error(row_num, 'Missing email address')
                    failed += 1
                    continue
                
                try:
                    validate_email(contact_data['email'])
                except ValidationError:
                    import_record.add_error(row_num, 'Invalid email address')
                    failed += 1
                    continue
                
                # Check for duplicates
                existing_contact = Contact.objects.filter(
                    user=user,
                    email=contact_data['email']
                ).first()
                
                if existing_contact:
                    if options.get('skip_duplicates', True):
                        duplicates += 1
                        continue
                    elif options.get('update_existing', False):
                        # Update existing contact
                        for field, value in contact_data.items():
                            if value and hasattr(existing_contact, field):
                                setattr(existing_contact, field, value)
                        existing_contact.save()
                        successful += 1
                        continue
                
                # Create new contact
                contact = Contact.objects.create(user=user, **contact_data)
                
                # Add to target list if specified
                if options.get('target_list'):
                    contact.lists.add(options['target_list'])
                
                successful += 1
                
            except Exception as e:
                import_record.add_error(row_num, str(e))
                failed += 1
        
        # Update import record
        import_record.successful_imports = successful
        import_record.failed_imports = failed
        import_record.duplicates_found = duplicates
        import_record.save()
        
        # Update target list count
        if options.get('target_list'):
            options['target_list'].update_contact_count()
        
        return {
            'successful': successful,
            'failed': failed,
            'duplicates': duplicates,
            'total': len(contacts_data)
        }
    
    def _map_contact_fields(self, row_data, field_mapping):
        """Map CSV/Excel fields to contact model fields"""
        contact_data = {}
        
        for model_field, possible_names in field_mapping.items():
            for name in possible_names:
                if name in row_data and row_data[name]:
                    contact_data[model_field] = row_data[name]
                    break
        
        return contact_data
    
    def export_contacts(self, user, contact_filter=None, format='csv'):
        """Export contacts to CSV/Excel"""
        try:
            # Get contacts
            contacts = user.contacts.filter(is_active=True)
            
            if contact_filter:
                contacts = contacts.filter(**contact_filter)
            
            # Prepare data
            export_data = []
            for contact in contacts:
                export_data.append({
                    'email': contact.email,
                    'first_name': contact.first_name or '',
                    'last_name': contact.last_name or '',
                    'phone': contact.phone or '',
                    'company': contact.company or '',
                    'job_title': contact.job_title or '',
                    'city': contact.city or '',
                    'country': contact.country or '',
                    'status': contact.status,
                    'engagement_score': contact.engagement_score,
                    'subscribed_at': contact.subscribed_at.isoformat() if contact.subscribed_at else '',
                    'lists': ', '.join([lst.name for lst in contact.lists.all()]),
                    'tags': ', '.join([tag.name for tag in contact.tags.all()]),
                })
            
            if format == 'csv':
                return self._export_to_csv(export_data)
            elif format == 'excel':
                return self._export_to_excel(export_data)
            else:
                raise ValueError('Unsupported export format')
                
        except Exception as e:
            logger.error(f"Contact export error: {str(e)}")
            raise e
    
    def _export_to_csv(self, data):
        """Export data to CSV format"""
        if not data:
            return ''
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    def _export_to_excel(self, data):
        """Export data to Excel format"""
        if not data:
            return b''
        
        df = pd.DataFrame(data)
        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        
        return output.getvalue()
    
    def bulk_update_contacts(self, contact_ids, updates):
        """Bulk update multiple contacts"""
        try:
            with transaction.atomic():
                contacts = Contact.objects.filter(id__in=contact_ids)
                updated_count = 0
                
                for contact in contacts:
                    for field, value in updates.items():
                        if hasattr(contact, field):
                            setattr(contact, field, value)
                    contact.save()
                    updated_count += 1
                
                logger.info(f"Bulk updated {updated_count} contacts")
                return {'success': True, 'updated_count': updated_count}
                
        except Exception as e:
            logger.error(f"Bulk contact update error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_contact_statistics(self, user):
        """Get contact statistics for user"""
        try:
            contacts = user.contacts.filter(is_active=True)
            
            stats = {
                'total_contacts': contacts.count(),
                'active_contacts': contacts.filter(status='ACTIVE').count(),
                'unsubscribed_contacts': contacts.filter(status='UNSUBSCRIBED').count(),
                'bounced_contacts': contacts.filter(status='BOUNCED').count(),
                'avg_engagement_score': contacts.aggregate(
                    avg_score=models.Avg('engagement_score')
                )['avg_score'] or 0,
                'contacts_added_today': contacts.filter(
                    created_at__date=timezone.now().date()
                ).count(),
                'contacts_added_this_week': contacts.filter(
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count(),
                'contacts_added_this_month': contacts.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count(),
            }
            
            # Top countries
            top_countries = contacts.values('country').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            stats['top_countries'] = list(top_countries)
            
            # Top companies
            top_companies = contacts.filter(
                company__isnull=False
            ).exclude(
                company=''
            ).values('company').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            stats['top_companies'] = list(top_companies)
            
            return stats
            
        except Exception as e:
            logger.error(f"Contact statistics error: {str(e)}")
            return {}

