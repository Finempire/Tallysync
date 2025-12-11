from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.users.models import RegisterTenantView, UserProfileView

def ping(request):
    return HttpResponse('pong')

print("DEBUG: Loading config.urls_public", flush=True)

urlpatterns = [
    path('admin-public/', admin.site.urls),
    path('ping/', ping),
    path('api/v1/auth/register/', RegisterTenantView.as_view(), name='register'),
    path('api/v1/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/profile/', UserProfileView.as_view(), name='profile'),
    path('api/v1/auth/profile-test/', lambda r: HttpResponse('profile ok')),

    # Exposed App Routes for Public Tenant (Localhost Dev)
    path('api/v1/companies/', include('apps.companies.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/bank-statements/', include('apps.bank_statements.urls')),
    path('api/v1/vouchers/', include('apps.vouchers.urls')),
    path('api/v1/tally/', include('apps.tally_connector.urls')),
    path('api/v1/gst/', include('apps.gst.urls')),
    path('api/v1/invoices/', include('apps.invoices.urls')),
    path('api/v1/payroll/', include('apps.payroll.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
