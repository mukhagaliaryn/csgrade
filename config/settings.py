from pathlib import Path
from decouple import config
from django.contrib import messages
from django.utils.translation import gettext_lazy as _


BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS").split(",")


# Applications
# ----------------------------------------------------------------------------------------------------------------------
INSTALLED_APPS = [
    "admin_interface",
    "colorfield",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ckeditor",
    "tailwind",
    "ui",
    "core.apps.CoreConfig",

    # apps...
    "apps.main.apps.MainConfig",
    "apps.manager.apps.ManagerConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DEBUG:
    INSTALLED_APPS += ["django_browser_reload"]
    MIDDLEWARE += [
        "django_browser_reload.middleware.BrowserReloadMiddleware",
    ]

ROOT_URLCONF = "config.urls"
AUTH_USER_MODEL = "core.User"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "ui/templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# DATABASE
# ----------------------------------------------------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_USER_PASSWORD"),
        "HOST": "localhost",
        "PORT": "",
    }
}


# Password validation
# ----------------------------------------------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# ----------------------------------------------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

LANGUAGES = (
    ("kk", _("Kazakh")),
    ("ru", _("Russian")),
    ("en", _("English")),
)

LOCALE_PATHS = [BASE_DIR / "locales"]


# Static files (CSS, JavaScript, Images)
# ----------------------------------------------------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STATICFILES_DIRS = [BASE_DIR / "ui/static"]


# Tailwind settings
# ----------------------------------------------------------------------------------------------------------------------
TAILWIND_APP_NAME = "ui"

# Messages
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

MESSAGE_TAGS = {
    messages.SUCCESS: 'text-green-600',
    messages.WARNING: 'text-amber-600',
    messages.INFO: 'text-blue-600',
    messages.ERROR: 'text-red-600',
}


# CORS Settings
# ----------------------------------------------------------------------------------------------------------------------
X_FRAME_OPTIONS = "SAMEORIGIN"
SILENCED_SYSTEM_CHECKS = ["security.W019"]


# Authentication settings
# ----------------------------------------------------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "core.utils.db.backends.EmailOrIINBackend",
]

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/auth/login/'
LOGIN_URL = '/auth/login/'


# CKEditor settings
# ----------------------------------------------------------------------------------------------------------------------
CKEDITOR_UPLOAD_PATH = "uploads/"

CKEDITOR_CONFIGS = {
    "default": {
        "skin": "moono-lisa",
        "defaultLanguage": "ru",
        "width": 840,
        "height": 420,
        "removePlugins": "autogrow",

        "autogrow": [
            {
                "autogrow": "styles",
                "items": ["Format"]
            },
            {
                "name": "basicstyles",
                "items": ["Bold", "Italic", "Underline", "-", "RemoveFormat"]
            },
            {
                "name": "paragraph",
                "items": [
                    "NumberedList", "BulletedList", "-",
                    'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock',
                ]
            },
            {
                'name': 'insert',
                'items': ['Image', 'Table', 'Mathjax', ]
            },
            {
                'name': 'document',
                'items': ['Source', '-', 'Preview', '-', 'Maximize']
            },
        ],
        'format_tags': 'p;h2;h3;h4',
        'mathJaxLib': 'https://cdn.jsdelivr.net/npm/mathjax@2/MathJax.js?config=TeX-AMS_HTML',
        'tabSpaces': 4,

        'image_upload_url': '/ckeditor/upload/',
        'filebrowserUploadUrl': '/ckeditor/upload/',
        'filebrowserBrowseUrl': '/ckeditor/browse/',

        'extraPlugins': ','.join([
            'mathjax',
            'uploadimage',
            'autogrow',
            'clipboard',
            'dialog',
            'dialogui',
            'elementspath',
        ]),
    }
}


OPENAI_API_KEY = config("OPENAI_API_KEY")
