"""
Django settings for wedding_project project.
Updated by Django Architect RO for Stability (Render + Cloudinary + Whitenoise).
"""
import os
from django.utils.translation import gettext_lazy as _
import dj_database_url
from pathlib import Path
import dotenv

# Load environment variables from .env file (if it exists)
dotenv.load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
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

# Application definition
INSTALLED_APPS = [
    # 1. Cloudinary apps FIRST
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
    'whitenoise.middleware.WhiteNoiseMiddleware', # Critical for static files on Render
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
            ],
        },
    },
]

WSGI_APPLICATION = 'wedding_project.wsgi.application'

# Database
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
LOGIN_REDIRECT_URL = '/dashboard/'

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
# === STATIC & MEDIA FILES (FIXED CONFIGURATION)         ===
# ==========================================================

# 1. STATIC FILES (CSS, JS, Admin) -> Render via Whitenoise
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') # Standard path for collectstatic
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# 2. MEDIA FILES (Uploads) -> Cloudinary
MEDIA_URL = '/media/' # Cloudinary will replace this URL dynamically
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Configurare Cloudinary Keys
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
}

# --- CONFIGURARE STORAGES (FAILSAFE MODE) ---
STORAGES = {
    # FIX FINAL: Folosim stocarea standard Django.
    # Dezactivăm complet procesarea WhiteNoise la build (fără compresie, fără hash).
    # Elimină orice risc de eroare "FileNotFound" la deploy.
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
    # 2. Gestionarea fișierelor media (Upload-uri)
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

# Comutăm pe Cloudinary dacă avem chei sau suntem pe Render
if 'RENDER' in os.environ:
    if not os.environ.get('CLOUDINARY_API_KEY'):
        print("❌ EROARE CRITICĂ: Lipsește CLOUDINARY_API_KEY pe Render!")
    else:
        USE_CLOUDINARY = True
        print("✅ PRODUCȚIE: Configurare Cloudinary Activată pentru Media.")
elif os.environ.get('CLOUDINARY_API_KEY'):
    USE_CLOUDINARY = True
    print("✅ LOCAL: Configurare Cloudinary Activată pentru Media.")

if USE_CLOUDINARY:
    STORAGES["default"]["BACKEND"] = "cloudinary_storage.storage.MediaCloudinaryStorage"

# Legacy Support
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