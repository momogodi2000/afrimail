# backend/middleware.py

from django.utils import timezone
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.conf import settings
from .models import UserActivity, ApiUsage
import time
import logging

logger = logging.getLogger(__name__)


class UserActivityMiddleware:
    """
    Middleware to track user activity and handle session management
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process request
        start_time = time.time()
        
        # Check session validity for authenticated users
        if request.user.is_authenticated:
            self._check_session_validity(request)
        
        response = self.get_response(request)
        
        # Log API usage if this is an API endpoint
        if request.path.startswith('/api/') and request.user.is_authenticated:
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            self._log_api_usage(request, response, response_time)
        
        return response
    
    def _check_session_validity(self, request):
        """Check if user session is still valid"""
        try:
            # Check session timeout
            last_activity = request.session.get('last_activity')
            if last_activity:
                last_activity_time = timezone.datetime.fromisoformat(last_activity)
                session_timeout = timezone.timedelta(
                    seconds=getattr(settings, 'SESSION_COOKIE_AGE', 3600)
                )
                
                if timezone.now() - last_activity_time > session_timeout:
                    # Session expired
                    UserActivity.log_activity(
                        user=request.user,
                        activity_type='SESSION_EXPIRED',
                        description='Session expired due to inactivity',
                        request=request
                    )
                    logout(request)
                    return
            
            # Update last activity
            request.session['last_activity'] = timezone.now().isoformat()
            
            # Check for suspicious activity (optional)
            self._check_suspicious_activity(request)
            
        except Exception as e:
            logger.error(f"Session validity check error: {str(e)}")
    
    def _check_suspicious_activity(self, request):
        """Check for suspicious user activity"""
        try:
            # Check for IP changes (warn but don't block)
            stored_ip = request.session.get('ip_address')
            current_ip = self._get_client_ip(request)
            
            if stored_ip and stored_ip != current_ip:
                UserActivity.log_activity(
                    user=request.user,
                    activity_type='IP_CHANGE',
                    description=f'IP changed from {stored_ip} to {current_ip}',
                    request=request
                )
                request.session['ip_address'] = current_ip
            
        except Exception as e:
            logger.error(f"Suspicious activity check error: {str(e)}")
    
    def _log_api_usage(self, request, response, response_time):
        """Log API usage for analytics"""
        try:
            ApiUsage.log_request(
                user=request.user,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                response_time=response_time,
                request=request
            )
        except Exception as e:
            logger.error(f"API usage logging error: {str(e)}")
    
    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityMiddleware:
    """
    Enhanced security middleware for AfriMail Pro
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Pre-process security checks
        if not self._security_check(request):
            return JsonResponse({'error': 'Security check failed'}, status=403)
        
        response = self.get_response(request)
        
        # Add security headers
        self._add_security_headers(response)
        
        return response
    
    def _security_check(self, request):
        """Perform security checks"""
        try:
            # Rate limiting check (basic implementation)
            if self._check_rate_limit(request):
                return False
            
            # Check for malicious patterns in request
            if self._check_malicious_patterns(request):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Security check error: {str(e)}")
            return True  # Allow request on error to avoid breaking functionality
    
    def _check_rate_limit(self, request):
        """Basic rate limiting"""
        try:
            if not request.user.is_authenticated:
                # Basic rate limiting for anonymous users
                ip = self._get_client_ip(request)
                cache_key = f"rate_limit_{ip}"
                
                from django.core.cache import cache
                current_requests = cache.get(cache_key, 0)
                
                if current_requests > 100:  # 100 requests per minute for anonymous users
                    logger.warning(f"Rate limit exceeded for IP: {ip}")
                    return True
                
                cache.set(cache_key, current_requests + 1, 60)  # 1 minute window
            
            return False
            
        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            return False
    
    def _check_malicious_patterns(self, request):
        """Check for malicious patterns in request"""
        try:
            # Check User-Agent for bots/scanners
            user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
            malicious_agents = [
                'sqlmap', 'nmap', 'nikto', 'dirb', 'dirbuster',
                'wget', 'curl', 'python-requests'
            ]
            
            for agent in malicious_agents:
                if agent in user_agent:
                    logger.warning(f"Malicious user agent detected: {user_agent}")
                    return True
            
            # Check for SQL injection patterns
            suspicious_params = []
            for param, value in request.GET.items():
                if isinstance(value, str):
                    suspicious_patterns = [
                        'union select', 'drop table', 'insert into',
                        '<script', 'javascript:', 'onload=',
                        '../', '..\\', '/etc/passwd'
                    ]
                    
                    for pattern in suspicious_patterns:
                        if pattern in value.lower():
                            suspicious_params.append((param, value))
            
            if suspicious_params:
                logger.warning(f"Suspicious parameters detected: {suspicious_params}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Malicious pattern check error: {str(e)}")
            return False
    
    def _add_security_headers(self, response):
        """Add security headers to response"""
        try:
            # Content Security Policy
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' cdn.jsdelivr.net cdnjs.cloudflare.com; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )
            
            # Additional security headers
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
            
            # HSTS for production
            if not settings.DEBUG:
                response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
        except Exception as e:
            logger.error(f"Security headers error: {str(e)}")
    
    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class MaintenanceMiddleware:
    """
    Maintenance mode middleware
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if maintenance mode is enabled
        from django.core.cache import cache
        maintenance_mode = cache.get('maintenance_mode', False)
        
        if maintenance_mode:
            # Allow superusers to access during maintenance
            if request.user.is_authenticated and request.user.is_super_admin:
                response = self.get_response(request)
                response['X-Maintenance-Mode'] = 'active'
                return response
            
            # Return maintenance page for others
            from django.template.response import TemplateResponse
            return TemplateResponse(
                request,
                'maintenance.html',
                {'maintenance_message': cache.get('maintenance_message', 'Site under maintenance')},
                status=503
            )
        
        return self.get_response(request)
