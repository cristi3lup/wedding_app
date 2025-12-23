"""
Django settings for wedding_project project.
Updated by Django Architect RO for Production Stability (Render + Brevo + Allauth).
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

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-prod')

# If 'RENDER' is set, we are live, so Debug is False. Otherwise True.
DEBUG = 'RENDER' not in os.environ

# Allow the server URL to access the app
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
ALLOWED_HOSTS.append('invapp-romania.ro')
ALLOWED_HOSTS.append('www.invapp-romania.ro')

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# --- NEW: CSRF TRUSTED ORIGINS (CRITIC PENTRU RENDER) ---
# Previne eroarea 403 Forbidden la Login/Signup în producție
CSRF_TRUSTED_ORIGINS = ['https://invapp-romania.ro', 'https://www.invapp-romania.ro']
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')
# Pentru dezvoltare locală, uneori e nevoie și de localhost (dacă testezi https local)
if DEBUG:
    CSRF_TRUSTED_ORIGINS.extend(['http://localhost:8000', 'http://127.0.0.1:8000'])


# Application definition
INSTALLED_APPS = [
    # 'invapp' must be ABOVE 'allauth' to override templates
    'invapp',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 3rd Party Apps
    'django.contrib.sites', # Required by Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',

    # Social Providers
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Static files optimization
    'django.contrib.sessions.middleware.SessionMiddleware',
    # --- Custom Middleware to force Romanian default on phones ---
    'wedding_project.middleware.ForceDefaultLanguageMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# ==========================================================
# === AUTHENTICATION BACKENDS (CRITIC PENTRU LOGIN)      ===
# ==========================================================
AUTHENTICATION_BACKENDS = [
    # Necesar pentru logarea în /admin cu username si parola
    'django.contrib.auth.backends.ModelBackend',

    # Necesar pentru Allauth (logare cu Email, Facebook, Google)
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

# ==========================================================
# === DATABASE                                           ===
# ==========================================================
DATABASES = {
    'default': dj_database_url.config(
        # Uses PostgreSQL on Render, falls back to SQLite locally
        default='sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3'),
        conn_max_age=600
    )
}

# ==========================================================
# === AUTHENTICATION & ALLAUTH (STRICT & STABLE)         ===
# ==========================================================
SITE_ID = 1  # Critical for Social Login

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Auth Settings
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_PASSWORD_REQUIRED = True

# Dezactivare totala a codurilor
ACCOUNT_LOGIN_BY_CODE_ENABLED = False

# --- UX Improvement: Afișează erori clare (ex: Mail neverificat) ---
ACCOUNT_PREVENT_ENUMERATION = False

# Email Verification
# Daca esti local si fara mail server, pune 'optional' sau 'none'
# Daca ai Brevo configurat, pune 'mandatory'
if DEBUG:
    ACCOUNT_EMAIL_VERIFICATION = 'optional'
else:
    ACCOUNT_EMAIL_VERIFICATION = 'mandatory'

ACCOUNT_CONFIRM_EMAIL_ON_GET = True
LOGIN_REDIRECT_URL = '/dashboard/'

# Social Account Settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none" # Trust Google/FB verification
SOCIALACCOUNT_QUERY_EMAIL = True

SOCIALACCOUNT_PROVIDERS = {
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'FIELDS': ['id', 'email', 'name', 'first_name', 'last_name'],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': True,
        'VERSION': 'v17.0',
    },
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'VERIFIED_EMAIL': True,
    }
}

# ==========================================================
# === EMAIL CONFIGURATION (BREVO SMTP)                   ===
# ==========================================================
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    # 1. Production / Real Email Mode (SMTP via Brevo)
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    # Default to Brevo (Sendinblue), fallback to whatever is in env
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp-relay.brevo.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = True
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@invapp-romania.ro')

    # Force verification in production because we can send emails
    ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
    ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
else:
    # 2. Development Mode (Console)
    # Prints emails to the Terminal instead of sending.
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'local-dev@invapp.ro'

    # If we are debugging locally without email creds, make verification optional
    # so we don't get locked out of new accounts.
    if DEBUG:
        ACCOUNT_EMAIL_VERIFICATION = 'optional'
    else:
        # If we are in Prod but missing keys, something is wrong.
        ACCOUNT_EMAIL_VERIFICATION = 'none'

# ==========================================================
# === INTERNATIONALIZATION                               ===
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

# ==========================================================
# === STATIC & MEDIA FILES (CLOUDINARY SETUP)            ===
# ==========================================================

# 1. Static Files (CSS/JS) - Served by WhiteNoise
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# 2. Media Files (User Uploads) - Served by Cloudinary
MEDIA_URL = '/media/' # Cloudinary handles the actual URL generation
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Configurare Cloudinary
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
}

# Daca avem cheile setate (adica suntem gata de upload), folosim Cloudinary
if os.environ.get('CLOUDINARY_API_KEY'):
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
else:
    # Fallback pe disc local (doar pentru dev fara net sau fara chei)
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================================
# === STRIPE CONFIGURATION                               ===
# ==========================================================
STRIPE_LIVE_SECRET_KEY = os.environ.get("STRIPE_LIVE_SECRET_KEY", "")
STRIPE_TEST_SECRET_KEY = os.environ.get("STRIPE_TEST_SECRET_KEY", "")
STRIPE_TEST_PUBLISHABLE_KEY = os.environ.get("STRIPE_TEST_PUBLISHABLE_KEY", "")
STRIPE_LIVE_PUBLISHABLE_KEY = os.environ.get("STRIPE_LIVE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

STRIPE_TEST_MODE = True # Change to False when going live!

if STRIPE_TEST_MODE:
    STRIPE_SECRET_KEY = STRIPE_TEST_SECRET_KEY
    STRIPE_PUBLIC_KEY = STRIPE_TEST_PUBLISHABLE_KEY
else:
    STRIPE_SECRET_KEY = STRIPE_LIVE_SECRET_KEY
    STRIPE_PUBLIC_KEY = STRIPE_LIVE_PUBLISHABLE_KEY

# ==========================================================
# === SECURITY & PROXY SETTINGS                          ===
# ==========================================================
# Trust the 'X-Forwarded-Proto' header set by Render
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

if not DEBUG:
    # --- PRODUCTION SETTINGS ---
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True

    # Render Domain Dynamic Logic
    if RENDER_EXTERNAL_HOSTNAME:
        DOMAIN_URL = f'https://{RENDER_EXTERNAL_HOSTNAME}'
    else:
        DOMAIN_URL = 'https://invapp-romania.ro'
else:
    # --- LOCAL DEVELOPMENT SETTINGS ---
    # Facebook requires 'http' locally for localhost
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http'
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

    # Use localhost:8000 for local dev
    DOMAIN_URL = 'http://localhost:8000'

# LOGGING
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}