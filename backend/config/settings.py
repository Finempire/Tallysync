"""
Django settings for Tally ERP Automation SaaS - All Phases
"""

import os
print("DEBUG: LOADING CONFIG.SETTINGS FROM DISK", flush=True)
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,.localhost').split(',')

# Multi-tenancy
TENANT_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'apps.users',
    'apps.companies',
    'apps.bank_statements',
    'apps.vouchers',
    'apps.tally_connector',
    'apps.gst',
    'apps.invoices',
    'apps.payroll',
    'apps.reports',
    'apps.notifications',
]

SHARED_APPS_BASE = [
    'django_tenants',
    'apps.tenants',
    'apps.users',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'django_filters',
]

# Merge Tenant Apps into Shared so they are created in Public Schema (Localhost)
SHARED_APPS = list(SHARED_APPS_BASE) + [app for app in TENANT_APPS if app not in SHARED_APPS_BASE]

INSTALLED_APPS = list(SHARED_APPS)

TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"
DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

import dj_database_url

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': os.getenv('DB_NAME', 'tally_automation'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

if os.environ.get('DATABASE_URL'):
    db_config = dj_database_url.config(default=os.environ.get('DATABASE_URL'))
    db_config['ENGINE'] = 'django_tenants.postgresql_backend'
    DATABASES['default'] = db_config

MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'config.debug_middleware.TenantDebugMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
PUBLIC_SCHEMA_URLCONF = 'config.urls_public_v2'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
AUTH_USER_MODEL = 'users.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend', 'rest_framework.filters.SearchFilter'],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}

CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS_ALLOW_CREDENTIALS = True

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_TIMEZONE = 'Asia/Kolkata'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Tally Config
TALLY_CONFIG = {'DEFAULT_PORT': 9000, 'TIMEOUT': 30, 'RETRY_ATTEMPTS': 3}

# GST Config
GST_CONFIG = {
    'GSP_API_URL': os.getenv('GSP_API_URL', ''),
    'GSP_CLIENT_ID': os.getenv('GSP_CLIENT_ID', ''),
    'GSP_CLIENT_SECRET': os.getenv('GSP_CLIENT_SECRET', ''),
    'E_INVOICE_SANDBOX': os.getenv('E_INVOICE_SANDBOX', 'True') == 'True',
}

# OCR Config
OCR_CONFIG = {
    'PROVIDER': os.getenv('OCR_PROVIDER', 'google'),  # google or aws
    'GOOGLE_CREDENTIALS': os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''),
}

# Razorpay
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')

# Email
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@tallysync.com'

# WhatsApp Business API
WHATSAPP_API_URL = os.getenv('WHATSAPP_API_URL', '')
WHATSAPP_API_TOKEN = os.getenv('WHATSAPP_API_TOKEN', '')
