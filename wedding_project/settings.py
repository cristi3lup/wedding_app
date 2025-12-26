"""
Django settings for wedding_project project.
Updated for Production on Render by Django Architect RO.
"""
import os
from pathlib import Path
import dj_database_url
# Folosim python-dotenv doar dacă există fișierul .env (Local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-default-key-for-dev')

# SECURITY WARNING: don't run with debug turned on in production!
# Pe Render, asigură-te că Environment Variable 'RENDER' este setată (de obicei e implicită sau o adaugi tu)
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

if RENDER_EXTERNAL_HOSTNAME:
    DEBUG = False
else:
    DEBUG = True

ALLOWED_HOSTS = []
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    ALLOWED_HOSTS.append('invapp-romania.ro') # Domeniul tău custom
    ALLOWED_HOSTS.append('www.invapp-romania.ro')
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required by allauth

    # Third party apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'tailwind',
    'theme',
    'crispy_forms',
    'crispy_tailwind',

    # Local apps
    'invapp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WHITENOISE TREBUIE SĂ FIE AICI (Imediat după SecurityMiddleware)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Adaugă middleware-ul Allauth
    'allauth.account.middleware.AccountMiddleware',
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
                'django.template.context_processors.request', # Required by allauth
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'invapp.context_processors.add_plans_to_context', # Context processor-ul tau
            ],
        },
    },
]

WSGI_APPLICATION = 'wedding_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

if not DEBUG:
    # Setări Producție (Render PostgreSQL)
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600
        )
    }
else:
    # Setări Local (SQLite)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth_password_validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'ro'
TIME_ZONE = 'Europe/Bucharest'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
# Folderul unde pui tu fișierele statice (imagini, css custom) în timpul dezvoltării
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
# Folderul unde 'collectstatic' va aduna TOATE fișierele statice pentru producție
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Configurare Tailwind
TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = [
    "127.0.0.1",
]
NPM_BIN_PATH = "C:/Program Files/nodejs/npm.cmd"  # Ajustează pentru Localhost dacă e nevoie, pe Render nu contează

# WhiteNoise Configuration - CRITIC PENTRU RENDER
if not DEBUG:
    # Comprimare și caching eficient pentru producție
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- ALLAUTH CONFIGURATION (STRICT MODE) ---
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Flux autentificare
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'mandatory' if not DEBUG else 'optional'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_BY_CODE_ENABLED = False  # Dezactivat explicit conform regulilor tale

LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'index'

# Email Configuration
if not DEBUG:
    # Setări pentru producție (ex: SendGrid, Mailgun etc.)
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST')
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = True
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')
else:
    # Prinde email-urile în consolă pe Localhost
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Stripe Configuration
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")