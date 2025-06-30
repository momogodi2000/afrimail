
# backend/apps.py

from django.apps import AppConfig


class BackendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend'
    verbose_name = 'AfriMail Pro Backend'
    
    def ready(self):
        # Import signal handlers
        import backend.signals
        
        # Import tasks to ensure they're registered
        import backend.tasks

