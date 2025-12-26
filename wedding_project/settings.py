"""
Django settings for wedding_project project.
STABLE VERSION: Cloudinary for Media, Whitenoise (Simple) for Static.
"""
import os
from django.utils.translation import gettext_lazy as _
import dj_database_url
from pathlib import Path
import dotenv

# Load environment variables
dotenv.load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================================
# === CORE SETTINGS                                      ===
# ==========================================================

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-prod')
DEBUG = 'RENDER' not in os.environ

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'invapp-romania.ro', 'www.invapp-romania.ro']
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# CSRF
CSRF_TRUSTED_ORIGINS = ['https://invapp-romania.ro', 'https://www.invapp-romania.ro']
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')
if DEBUG:
    CSRF_TRUSTED_ORIGINS.extend(['http://localhost:8000', 'http://127.0.0.1:8000'])

INSTALLED_APPS = [
    # 1. Storage & Static - Ordinea e importanta
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'cloudinary',

    # Apps
    'invapp',
    'import_export',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',

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
    'whitenoise.middleware.WhiteNoiseMiddleware', # SERVESTE FISIERELE STATICE (CSS/JS)
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
                # Context processor pentru imaginile dinamice din Admin
                'invapp.context_processors.site_assets',
            ],
        },
    },
]

WSGI_APPLICATION = 'wedding_project.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3'),
        conn_max_age=600
    )
}

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

ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_PASSWORD_REQUIRED = True
ACCOUNT_LOGIN_BY_CODE_ENABLED = False
ACCOUNT_PREVENT_ENUMERATION = False
ACCOUNT_CONFIRM_EMAIL_ON_GET = True

# FIX: Redirectăm pe Home după logout pentru a evita erorile de permisiuni
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_QUERY_EMAIL = True

SOCIALACCOUNT_PROVIDERS = {
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'FIELDS': ['id', 'email', 'name', 'first_name', 'last_name', 'picture'],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': True,
        'VERSION': 'v17.0',
    },
    'google': {'SCOPE': ['profile', 'email'], 'AUTH_PARAMS': {'access_type': 'online'}, 'VERIFIED_EMAIL': True}
}

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
# === I18N                                               ===
# ==========================================================
LANGUAGE_CODE = 'ro'
LANGUAGES = [('ro', _('Romanian')), ('en', _('English'))]
TIME_ZONE = 'Europe/Bucharest'
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]

# ==========================================================
# === STATIC & MEDIA FILES (STABILITY MODE)              ===
# ==========================================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
    'SECURE_URL': True,
}

# CONFIGURARE STORAGES
# 1. Static (CSS/JS): Folosim standardul Django. Whitenoise va servi fișierele oricum.
# Aceasta evită erorile de compresie la build.
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

# 2. Media (Uploads): Cloudinary doar dacă avem chei.
if 'RENDER' in os.environ:
    if not os.environ.get('CLOUDINARY_API_KEY'):
        print("❌ EROARE: Lipsește CLOUDINARY_API_KEY pe Render!")
    else:
        STORAGES["default"]["BACKEND"] = "cloudinary_storage.storage.MediaCloudinaryStorage"
elif os.environ.get('CLOUDINARY_API_KEY'):
    STORAGES["default"]["BACKEND"] = "cloudinary_storage.storage.MediaCloudinaryStorage"

# Legacy Support (pentru librării vechi)
STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]
DEFAULT_FILE_STORAGE = STORAGES["default"]["BACKEND"]

# ==========================================================
# === ALTELE                                             ===
# ==========================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STRIPE_LIVE_SECRET_KEY = os.environ.get("STRIPE_LIVE_SECRET_KEY", "")
STRIPE_TEST_SECRET_KEY = os.environ.get("STRIPE_TEST_SECRET_KEY", "")
STRIPE_TEST_PUBLISHABLE_KEY = os.environ.get("STRIPE_TEST_PUBLISHABLE_KEY", "")
STRIPE_LIVE_PUBLISHABLE_KEY = os.environ.get("STRIPE_LIVE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_TEST_MODE = True

if STRIPE_TEST_MODE:
    STRIPE_SECRET_KEY = STRIPE_TEST_SECRET_KEY
    STRIPE_PUBLIC_KEY = STRIPE_TEST_PUBLISHABLE_KEY
else:
    STRIPE_SECRET_KEY = STRIPE_LIVE_SECRET_KEY
    STRIPE_PUBLIC_KEY = STRIPE_LIVE_PUBLISHABLE_KEY

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