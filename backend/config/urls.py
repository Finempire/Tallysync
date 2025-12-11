"""
Main URL Configuration for Tally ERP Automation SaaS
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.http import HttpResponse
print("DEBUG: LOADING CONFIG.URLS", flush=True)
from apps.users.models import UserProfileView

urlpatterns = [
    path('ping-root-top/', lambda r: HttpResponse('top ok')),
    path('admin-root/', admin.site.urls),
    
    # API v1 endpoints
    path('api/v1/', include([
        path('ping-root/', lambda r: HttpResponse('root ok')),
        path('auth/profile/', UserProfileView.as_view(), name='profile-root'),
        # Authentication
        path('auth/', include('apps.users.urls')),
        
        # Core modules
        path('companies/', include('apps.companies.urls')),
        path('bank-statements/', include('apps.bank_statements.urls')),
        path('vouchers/', include('apps.vouchers.urls')),
        path('tally/', include('apps.tally_connector.urls')),
        
        # GST & Compliance
        path('gst/', include('apps.gst.urls')),
        
        # Invoice OCR
        path('invoices/', include('apps.invoices.urls')),
        
        # Payroll
        path('payroll/', include('apps.payroll.urls')),
        
        # Reports & Analytics
        path('reports/', include('apps.reports.urls')),
        
        # Notifications
        path('notifications/', include('apps.notifications.urls')),
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
