# backend/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from .models import (
    CustomUser, UserProfile, Contact, ContactList, ContactTag,
    EmailDomainConfig, EmailTemplate, EmailCampaign
)
import re


# Authentication Forms
class LoginForm(forms.Form):
    """User login form"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('email', css_class='mb-3'),
            Field('password', css_class='mb-3'),
            Field('remember_me', css_class='form-check mb-3'),
            Submit('submit', 'Sign In', css_class='btn btn-primary w-100')
        )


class RegistrationForm(forms.ModelForm):
    """User registration form"""
    
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a strong password'
        }),
        help_text='Password must be at least 8 characters with uppercase, lowercase, number, and special character.'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )
    marketing_consent = forms.BooleanField(
        required=False,
        label='I agree to receive marketing emails',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    terms_accepted = forms.BooleanField(
        required=True,
        label='I agree to the Terms of Service and Privacy Policy',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'email', 'company', 'phone',
            'country', 'city', 'industry', 'company_size', 'company_website'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+237 6XX XXX XXX'}),
            'country': forms.Select(attrs={'class': 'form-select'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'industry': forms.Select(attrs={'class': 'form-select'}),
            'company_size': forms.Select(attrs={'class': 'form-select'}),
            'company_website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://yourcompany.com'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-3'),
                Column('last_name', css_class='form-group col-md-6 mb-3'),
            ),
            Field('email', css_class='mb-3'),
            Field('company', css_class='mb-3'),
            Row(
                Column('phone', css_class='form-group col-md-6 mb-3'),
                Column('country', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('city', css_class='form-group col-md-6 mb-3'),
                Column('industry', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('company_size', css_class='form-group col-md-6 mb-3'),
                Column('company_website', css_class='form-group col-md-6 mb-3'),
            ),
            Field('password', css_class='mb-3'),
            Field('password_confirm', css_class='mb-3'),
            Field('marketing_consent', css_class='form-check mb-3'),
            Field('terms_accepted', css_class='form-check mb-3'),
            Submit('submit', 'Create Account', css_class='btn btn-primary w-100')
        )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError('This email address is already registered.')
        return email
    
    def clean_password(self):
        password = self.cleaned_data.get('password')
        
        # Password strength validation
        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long.')
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        
        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number.')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character.')
        
        return password
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise ValidationError('Passwords do not match.')
        
        return cleaned_data


class PasswordResetForm(forms.Form):
    """Password reset request form"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autofocus': True
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('email', css_class='mb-3'),
            Submit('submit', 'Send Reset Link', css_class='btn btn-primary w-100')
        )


class ChangePasswordForm(forms.Form):
    """Change password form"""
    
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current password'
        })
    )
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('old_password', css_class='mb-3'),
            Field('new_password', css_class='mb-3'),
            Field('confirm_password', css_class='mb-3'),
            Submit('submit', 'Change Password', css_class='btn btn-primary')
        )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError('New passwords do not match.')
        
        return cleaned_data


# Contact Forms
class ContactForm(forms.ModelForm):
    """Individual contact form"""
    
    class Meta:
        model = Contact
        fields = [
            'email', 'first_name', 'last_name', 'phone', 'gender', 'date_of_birth',
            'address', 'city', 'state', 'country', 'postal_code',
            'company', 'job_title', 'industry', 'website',
            'source', 'utm_source', 'utm_medium', 'utm_campaign',
            'lists', 'tags'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'job_title': forms.TextInput(attrs={'class': 'form-control'}),
            'industry': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'source': forms.TextInput(attrs={'class': 'form-control'}),
            'utm_source': forms.TextInput(attrs={'class': 'form-control'}),
            'utm_medium': forms.TextInput(attrs={'class': 'form-control'}),
            'utm_campaign': forms.TextInput(attrs={'class': 'form-control'}),
            'lists': forms.SelectMultiple(attrs={'class': 'form-select', 'multiple': True}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'multiple': True}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter lists and tags by user
        self.fields['lists'].queryset = ContactList.objects.filter(user=user, is_active=True)
        self.fields['tags'].queryset = ContactTag.objects.filter(user=user)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('email', css_class='form-group col-md-12 mb-3'),
            ),
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-3'),
                Column('last_name', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('phone', css_class='form-group col-md-6 mb-3'),
                Column('gender', css_class='form-group col-md-6 mb-3'),
            ),
            Field('date_of_birth', css_class='mb-3'),
            Field('address', css_class='mb-3'),
            Row(
                Column('city', css_class='form-group col-md-4 mb-3'),
                Column('state', css_class='form-group col-md-4 mb-3'),
                Column('country', css_class='form-group col-md-4 mb-3'),
            ),
            Field('postal_code', css_class='mb-3'),
            HTML('<h5 class="mt-4">Professional Information</h5>'),
            Row(
                Column('company', css_class='form-group col-md-6 mb-3'),
                Column('job_title', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('industry', css_class='form-group col-md-6 mb-3'),
                Column('website', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<h5 class="mt-4">Source Tracking</h5>'),
            Row(
                Column('source', css_class='form-group col-md-6 mb-3'),
                Column('utm_source', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('utm_medium', css_class='form-group col-md-6 mb-3'),
                Column('utm_campaign', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<h5 class="mt-4">Organization</h5>'),
            Field('lists', css_class='mb-3'),
            Field('tags', css_class='mb-3'),
            FormActions(
                Submit('submit', 'Save Contact', css_class='btn btn-primary'),
                HTML('<a href="{% url "backend:contact_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )


class ContactListForm(forms.ModelForm):
    """Contact list form"""
    
    class Meta:
        model = ContactList
        fields = ['name', 'description', 'list_type', 'is_favorite']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'List Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'list_type': forms.Select(attrs={'class': 'form-select'}),
            'is_favorite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('name', css_class='mb-3'),
            Field('description', css_class='mb-3'),
            Field('list_type', css_class='mb-3'),
            Field('is_favorite', css_class='form-check mb-3'),
            FormActions(
                Submit('submit', 'Save List', css_class='btn btn-primary'),
                HTML('<a href="{% url "backend:contact_lists" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )


class ContactImportForm(forms.Form):
    """Contact import form"""
    
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        }),
        help_text='Upload a CSV or Excel file with contact information'
    )
    target_list = forms.ModelChoiceField(
        queryset=ContactList.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Optional: Add imported contacts to a specific list'
    )
    skip_duplicates = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Skip contacts with email addresses that already exist'
    )
    update_existing = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Update existing contacts with new information'
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['target_list'].queryset = ContactList.objects.filter(user=user, is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Field('csv_file', css_class='mb-3'),
            Field('target_list', css_class='mb-3'),
            Field('skip_duplicates', css_class='form-check mb-3'),
            Field('update_existing', css_class='form-check mb-3'),
            FormActions(
                Submit('submit', 'Import Contacts', css_class='btn btn-primary'),
                HTML('<a href="{% url "backend:contact_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )
    
    def clean_csv_file(self):
        file = self.cleaned_data.get('csv_file')
        
        if file:
            # Check file size (max 5MB)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError('File size cannot exceed 5MB.')
            
            # Check file extension
            valid_extensions = ['.csv', '.xlsx', '.xls']
            if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError('Please upload a CSV or Excel file.')
        
        return file


# Email Configuration Forms
class EmailDomainConfigForm(forms.ModelForm):
    """Email domain configuration form"""
    
    smtp_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'SMTP Password'
        }),
        help_text='Leave blank to keep existing password'
    )
    
    class Meta:
        model = EmailDomainConfig
        fields = [
            'domain_name', 'from_email', 'from_name', 'reply_to_email',
            'smtp_provider', 'smtp_host', 'smtp_port', 'smtp_username',
            'use_tls', 'use_ssl', 'daily_send_limit', 'monthly_send_limit',
            'is_default'
        ]
        widgets = {
            'domain_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'example.com'}),
            'from_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'noreply@example.com'}),
            'from_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Company'}),
            'reply_to_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'reply@example.com'}),
            'smtp_provider': forms.Select(attrs={'class': 'form-select'}),
            'smtp_host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'smtp.gmail.com'}),
            'smtp_port': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '587'}),
            'smtp_username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'username@gmail.com'}),
            'use_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'use_ssl': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'daily_send_limit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1000'}),
            'monthly_send_limit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '10000'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<h5>Domain Information</h5>'),
            Row(
                Column('domain_name', css_class='form-group col-md-6 mb-3'),
                Column('from_email', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('from_name', css_class='form-group col-md-6 mb-3'),
                Column('reply_to_email', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<h5 class="mt-4">SMTP Configuration</h5>'),
            Field('smtp_provider', css_class='mb-3'),
            Row(
                Column('smtp_host', css_class='form-group col-md-8 mb-3'),
                Column('smtp_port', css_class='form-group col-md-4 mb-3'),
            ),
            Row(
                Column('smtp_username', css_class='form-group col-md-6 mb-3'),
                Column('smtp_password', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column(
                    Field('use_tls', css_class='form-check'),
                    css_class='form-group col-md-6 mb-3'
                ),
                Column(
                    Field('use_ssl', css_class='form-check'),
                    css_class='form-group col-md-6 mb-3'
                ),
            ),
            HTML('<h5 class="mt-4">Send Limits</h5>'),
            Row(
                Column('daily_send_limit', css_class='form-group col-md-6 mb-3'),
                Column('monthly_send_limit', css_class='form-group col-md-6 mb-3'),
            ),
            Field('is_default', css_class='form-check mb-3'),
            FormActions(
                Submit('submit', 'Save Configuration', css_class='btn btn-primary'),
                HTML('<a href="{% url "backend:email_config_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )


# Campaign Forms
class EmailCampaignForm(forms.ModelForm):
    """Email campaign form"""
    
    class Meta:
        model = EmailCampaign
        fields = [
            'name', 'description', 'campaign_type', 'email_config',
            'subject', 'from_name', 'reply_to_email', 'html_content',
            'text_content', 'contact_lists', 'scheduled_at', 'send_immediately',
            'track_opens', 'track_clicks', 'track_unsubscribes', 'priority'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Campaign Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'campaign_type': forms.Select(attrs={'class': 'form-select'}),
            'email_config': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email Subject'}),
            'from_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sender Name'}),
            'reply_to_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'reply@example.com'}),
            'html_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 15, 'id': 'html-editor'}),
            'text_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'contact_lists': forms.SelectMultiple(attrs={'class': 'form-select', 'multiple': True}),
            'scheduled_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'send_immediately': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'track_opens': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'track_clicks': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'track_unsubscribes': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter by user
        self.fields['email_config'].queryset = EmailDomainConfig.objects.filter(
            user=user, is_active=True, domain_verified=True
        )
        self.fields['contact_lists'].queryset = ContactList.objects.filter(
            user=user, is_active=True
        )
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<h5>Campaign Information</h5>'),
            Field('name', css_class='mb-3'),
            Field('description', css_class='mb-3'),
            Row(
                Column('campaign_type', css_class='form-group col-md-6 mb-3'),
                Column('email_config', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<h5 class="mt-4">Email Content</h5>'),
            Field('subject', css_class='mb-3'),
            Row(
                Column('from_name', css_class='form-group col-md-6 mb-3'),
                Column('reply_to_email', css_class='form-group col-md-6 mb-3'),
            ),
            Field('html_content', css_class='mb-3'),
            Field('text_content', css_class='mb-3'),
            HTML('<h5 class="mt-4">Recipients</h5>'),
            Field('contact_lists', css_class='mb-3'),
            HTML('<h5 class="mt-4">Scheduling</h5>'),
            Field('send_immediately', css_class='form-check mb-3'),
            Field('scheduled_at', css_class='mb-3'),
            Field('priority', css_class='mb-3'),
            HTML('<h5 class="mt-4">Tracking Options</h5>'),
            Row(
                Column(
                    Field('track_opens', css_class='form-check'),
                    css_class='form-group col-md-4 mb-3'
                ),
                Column(
                    Field('track_clicks', css_class='form-check'),
                    css_class='form-group col-md-4 mb-3'
                ),
                Column(
                    Field('track_unsubscribes', css_class='form-check'),
                    css_class='form-group col-md-4 mb-3'
                ),
            ),
            FormActions(
                Submit('submit', 'Save Campaign', css_class='btn btn-primary'),
                Submit('save_and_send', 'Save and Send', css_class='btn btn-success ms-2'),
                HTML('<a href="{% url "backend:campaign_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        send_immediately = cleaned_data.get('send_immediately')
        scheduled_at = cleaned_data.get('scheduled_at')
        
        if not send_immediately and not scheduled_at:
            raise ValidationError('Please either schedule the campaign or select "Send Immediately".')
        
        if scheduled_at and scheduled_at <= timezone.now():
            raise ValidationError('Scheduled time must be in the future.')
        
        return cleaned_data


class EmailTemplateForm(forms.ModelForm):
    """Email template form"""
    
    class Meta:
        model = EmailTemplate
        fields = ['name', 'description', 'template_type', 'subject', 'html_content', 'text_content', 'is_shared']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Template Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'template_type': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email Subject'}),
            'html_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 15, 'id': 'template-html-editor'}),
            'text_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'is_shared': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<h5>Template Information</h5>'),
            Field('name', css_class='mb-3'),
            Field('description', css_class='mb-3'),
            Field('template_type', css_class='mb-3'),
            HTML('<h5 class="mt-4">Email Content</h5>'),
            Field('subject', css_class='mb-3'),
            Field('html_content', css_class='mb-3'),
            Field('text_content', css_class='mb-3'),
            Field('is_shared', css_class='form-check mb-3'),
            FormActions(
                Submit('submit', 'Save Template', css_class='btn btn-primary'),
                HTML('<a href="{% url "backend:template_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )


# Search and Filter Forms
class ContactSearchForm(forms.Form):
    """Contact search and filter form"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search contacts...'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + Contact.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    contact_list = forms.ModelChoiceField(
        queryset=ContactList.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    country = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contact_list'].queryset = ContactList.objects.filter(user=user, is_active=True)


class CampaignSearchForm(forms.Form):
    """Campaign search and filter form"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search campaigns...'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + EmailCampaign.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    campaign_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + EmailCampaign.CAMPAIGN_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )