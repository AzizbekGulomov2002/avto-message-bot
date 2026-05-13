"""
Django settings for config project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR is the config directory (where settings.py is located)
BASE_DIR = Path(__file__).resolve().parent
# PROJECT_ROOT is the project root (python-messanger-bot)
PROJECT_ROOT = BASE_DIR.parent.parent

# Load environment variables from the project root.
load_dotenv(PROJECT_ROOT / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

allowed_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts.split(',') if host.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['*']

csrf_trusted_origins = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in csrf_trusted_origins.split(',')
    if origin.strip()
]

if os.getenv('DJANGO_USE_PROXY', 'False').lower() in ('true', '1', 'yes'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users.apps.UsersConfig',
    'messages.apps.MessagesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'taxi'),
        'USER': os.getenv('POSTGRES_USER', 'taxi'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'taxi'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}


JAZZMIN_SETTINGS = {
    # Branding
    "site_title":    "Taxi Messenger Bot",
    "site_header":   "Taxi Messenger Bot",
    "site_brand":    "Taxi Messenger Bot",
    "site_logo":     "images/taximessanger.png",
    "site_logo_classes": "img-circle",
    "site_icon":     "images/taximessanger.png",
    "login_logo":    "images/taximessanger.png",
    "login_logo_dark": "images/taximessanger.png",
    "welcome_sign":  "Taxi Messenger Bot Admin Paneliga xush kelibsiz",
    "copyright":     "Taxi Messenger Bot",

    # Search & UI
    "search_model": ["users.User", "users.UserPayment", "messages.ScheduleInterval", "messages.DurationOption"],
    "show_sidebar": True,
    "related_modal_active": False,
    
    "order_with_respect_to": [
        "users",
        "messages",
        "auth",       
    ],

    "icons": {
        # Users
        "users.User": "fas fa-users",
        "users.UserPayment": "fas fa-credit-card",
        
        # Messages App (Bot_Messages)
        "messages": "fas fa-comments",
        "bot_messages": "fas fa-comments",
        
        # Messages - Schedule intervals and duration options
        "messages.ScheduleInterval": "fas fa-calendar-alt",
        "messages.DurationOption": "fas fa-stopwatch",
        
        # Auth
        "auth.User": "fas fa-user-shield",
        "auth.Group": "fas fa-user-friends",
    },

    # Defaults
    "default_icon_parents":  "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    
    # Custom CSS for circular logo
    "custom_css": "admin/css/custom_styles.css",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_fixed":   True,
    "footer_fixed":   True,
    "sidebar_fixed":  True,
    "sidebar":        "sidebar-dark-navy",
    "theme":          "default",
    "button_classes": {
        "primary":   "btn-primary",
        "success":   "btn-success",
        "info":      "btn-info",
        "warning":   "btn-warning",
        "danger":    "btn-danger",
    },
}


# Password validation
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
LANGUAGE_CODE = 'uz-uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',  # Config static files (admin CSS, images)
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

