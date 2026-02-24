"""
Django settings for wedding_project project.
CORE REFACTOR V6:
- Languages: Restricted to RO and EN.
- Static Files: Standard Storage + Whitenoise Middleware (Safe Mode).
- Social Auth: Fail-safe for missing environment variables.
"""
import os
import sys
from django.utils.translation import gettext_lazy as _
import dj_database_url
from pathlib import Path
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================================
# === CORE SETTINGS                                      ===
# ==========================================================

# Use environment variable for DEBUG, defaulting to False for security
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-key-for-local-development-only'
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("The SECRET_KEY environment variable must be set in production.")

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'invapp-romania.ro', 'www.invapp-romania.ro']
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# CSRF
CSRF_TRUSTED_ORIGINS = ['https://invapp-romania.ro', 'https://www.invapp-romania.ro', 'https://*.invapp-romania.ro']
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')
if DEBUG:
    CSRF_TRUSTED_ORIGINS.extend(['http://localhost:8000', 'http://127.0.0.1:8000'])

INSTALLED_APPS = [
    # 1. Storage & Static - Order is important
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'cloudinary',
    'widget_tweaks',

    # Apps
    'invapp',
    'import_export',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sitemaps',  # Added for SEO

    # Auth & Social
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WHITENOISE MUST BE HERE (Position 2)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'wedding_project.middleware.ForceDefaultLanguageMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ROOT_URLCONF = 'wedding_project.urls'

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
                'invapp.context_processors.add_active_plan_to_context',
                'invapp.context_processors.site_assets',
                'invapp.context_processors.seo_settings',
            ],
        },
    },
]

# ==========================================================
# === SEO & ANALYTICS                                    ===
# ==========================================================
GOOGLE_SITE_VERIFICATION = os.environ.get('GOOGLE_SITE_VERIFICATION', '')
GA_MEASUREMENT_ID = os.environ.get('GA_MEASUREMENT_ID', '')
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')


WSGI_APPLICATION = 'wedding_project.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3'),
        conn_max_age=600
    )
}

# ==========================================================
# === STATIC & MEDIA FILES (SAFE MODE)                   ===
# ==========================================================

STATIC_URL = '/static/'

# Destination folder for static files
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Ensure directory exists
if not os.path.exists(STATIC_ROOT):
    try:
        os.makedirs(STATIC_ROOT, exist_ok=True)
    except OSError:
        pass

# Source folders for static files
STATICFILES_DIRS = []
LOCAL_STATIC_DIR = BASE_DIR / 'static'
if os.path.exists(LOCAL_STATIC_DIR):
    STATICFILES_DIRS.append(LOCAL_STATIC_DIR)

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
    'SECURE_URL': True,
}

# --- STORAGES CONFIGURATION ---
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

if not DEBUG:
    # Tell Whitenoise to check source if file not found in staticfiles/
    WHITENOISE_USE_FINDERS = True

    # Media Files via Cloudinary in production
    if os.environ.get('CLOUDINARY_API_KEY'):
        STORAGES["default"]["BACKEND"] = "cloudinary_storage.storage.MediaCloudinaryStorage"

# --- LEGACY SUPPORT ---
STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]
DEFAULT_FILE_STORAGE = STORAGES["default"]["BACKEND"]

# ==========================================================
# === I18N (LANGUAGE CONFIG)                             ===
# ==========================================================
LANGUAGE_CODE = 'ro'

LANGUAGES = [
    ('ro', _('Romanian')),
    ('en', _('English')),
]

TIME_ZONE = 'Europe/Bucharest'
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]

DATE_INPUT_FORMATS = [
    '%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d',
]

DATETIME_INPUT_FORMATS = [
    '%d/%m/%Y %H:%M:%S',
    '%d/%m/%Y %H:%M',
    '%d/%m/%Y',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d',
]


# ==========================================================
# === AUTH & EMAIL                                       ===
# ==========================================================
SITE_ID = 1

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Allauth Settings (Django 5+)
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_PASSWORD_REQUIRED = True
ACCOUNT_LOGIN_BY_CODE_ENABLED = False
ACCOUNT_PREVENT_ENUMERATION = False
ACCOUNT_CONFIRM_EMAIL_ON_GET = True

# --- SOCIAL ACCOUNT SETTINGS ---
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_ADAPTER = 'allauth.socialaccount.adapter.DefaultSocialAccountAdapter'

SOCIALACCOUNT_PROVIDERS = {
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'FIELDS': ['id', 'email', 'name', 'first_name', 'last_name', 'picture'],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': True,
        'VERSION': 'v17.0',
    },
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'VERIFIED_EMAIL': True,
    }
}

LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp-relay.brevo.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = True
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@invapp-romania.ro')
    ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
    ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'local-dev@invapp.ro'
    ACCOUNT_EMAIL_VERIFICATION = 'optional' if DEBUG else 'none'

# ==========================================================
# === OTHER                                              ===
# ==========================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================================
# === STRIPE CONFIGURATION                               ===
# ==========================================================
STRIPE_LIVE_SECRET_KEY = os.environ.get("STRIPE_LIVE_SECRET_KEY", "")
STRIPE_LIVE_PUBLISHABLE_KEY = os.environ.get("STRIPE_LIVE_PUBLISHABLE_KEY", "")

STRIPE_TEST_SECRET_KEY = os.environ.get("STRIPE_TEST_SECRET_KEY", "")
STRIPE_TEST_PUBLISHABLE_KEY = os.environ.get("STRIPE_TEST_PUBLISHABLE_KEY", "")

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# SWITCH LOGIC:
# Use LIVE keys if STRIPE_LIVE_MODE is explicitly 'True' in environment.
STRIPE_LIVE_MODE = os.environ.get("STRIPE_LIVE_MODE", "False") == "True"

if STRIPE_LIVE_MODE:
    STRIPE_SECRET_KEY = STRIPE_LIVE_SECRET_KEY
    STRIPE_PUBLIC_KEY = STRIPE_LIVE_PUBLISHABLE_KEY
    STRIPE_TEST_MODE = False
    print("💳 STRIPE: Running in LIVE MODE")
else:
    STRIPE_SECRET_KEY = STRIPE_TEST_SECRET_KEY
    STRIPE_PUBLIC_KEY = STRIPE_TEST_PUBLISHABLE_KEY
    STRIPE_TEST_MODE = True
    print("💳 STRIPE: Running in TEST MODE")

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

if not DEBUG:
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    DOMAIN_URL = f'https://{RENDER_EXTERNAL_HOSTNAME}' if RENDER_EXTERNAL_HOSTNAME else 'https://invapp-romania.ro'
else:
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http'
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    DOMAIN_URL = 'http://localhost:8000'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}
