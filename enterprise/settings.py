import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(*names, default=False):
    """Read a boolean environment variable, supporting the legacy names."""
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def env_list(*names, default=None):
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return [item.strip() for item in value.split(",") if item.strip()]
    return list(default or [])


DEBUG = env_bool("DJANGO_DEBUG", "DEBUG", default=False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-local-dev-only-do-not-deploy"
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY is not set. Refusing to start with DEBUG=False "
            "and no secret key configured — set it in the environment or .env."
        )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "ALLOWED_HOSTS", default=["*"] if DEBUG else [])

# HTTPS/security defaults are enabled for production and can be overridden when
# TLS is terminated elsewhere (for example, by a load balancer).
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv("SECURE_REFERRER_POLICY", "same-origin")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.humanize",
    "django.contrib.staticfiles",
    "account",
    "core",
    "notification",
    "assets.assetapp",
    "com_app.communication",
    "com_app.staff_events",
    "com_app.media_presence",
    "hr_apps.HRapp",
    "hr_apps.appraisals",
    "hr_apps.vacancy",
    "procurement.procureapp",
    "finance_app.finance",
    "risk_apps.governance",
    "risk_apps.risk",
    "risk_apps.compliance",
    "risk_apps.audit",
    "risk_apps.analytics",
    "mne.monitoring",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "enterprise.middleware.ErrorCaptureMiddleware",
    "core.middleware.EditDeleteAuthorizationMiddleware",
    "core.middleware.RequireLoginForModulesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "account.middleware.BlockExitedUserMiddleware",
    "core.middleware.RequestAuditMiddleware",
]

ROOT_URLCONF = "enterprise.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "enterprise.context_processors.system_catalog",
                "enterprise.context_processors.active_system_ui",
                "enterprise.context_processors.forum_activity",
                "core.context_processors.currency_context",
                "core.context_processors.global_dashboard",
                "core.context_processors.site_settings",
                "hr_apps.HRapp.context_processors.event_profile",
                "com_app.communication.context_processors.focus_areas",
                "notification.context_processors.notifications",
                "assets.assetapp.context_processors.asset_counts",
                "finance_app.finance.context_processors.finance_permissions",
            ],
            "builtins": [
                "core.templatetags.currency_tags",
            ],
        },
    }
]

if not DEBUG:
    # Avoid reparsing and recompiling templates on every request in production.
    TEMPLATES[0]["APP_DIRS"] = False
    TEMPLATES[0]["OPTIONS"]["loaders"] = [
        ("django.template.loaders.cached.Loader", [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ])
    ]

WSGI_APPLICATION = "enterprise.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60" if not DEBUG else "0")),
        "CONN_HEALTH_CHECKS": True,
    }
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})["timeout"] = int(
        os.getenv("SQLITE_TIMEOUT", "20")
    )

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Africa/Kampala")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
EDIT_GROUP_ACCESS_MINUTES = int(os.environ.get("EDIT_GROUP_ACCESS_MINUTES", "30"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "account.Profile"
AUTHENTICATION_BACKENDS = ["account.backends.ActiveUserBackend"]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/systems/"
LOGOUT_REDIRECT_URL = "/"
SITE_ID = 1

EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "RICE WN Support Team <godwithusakpan2015@gmail.com>")

STAFF_MONTHLY_MEETING_HOUR = int(os.getenv("STAFF_MONTHLY_MEETING_HOUR", "9"))
STAFF_MONTHLY_MEETING_MINUTE = int(os.getenv("STAFF_MONTHLY_MEETING_MINUTE", "0"))
STAFF_MONTHLY_MEETING_DURATION_HOURS = int(os.getenv("STAFF_MONTHLY_MEETING_DURATION_HOURS", "2"))
STAFF_MONTHLY_MEETING_TITLE = os.getenv("STAFF_MONTHLY_MEETING_TITLE", "Staff Monthly Meeting")
STAFF_MONTHLY_MEETING_DESCRIPTION = os.getenv("STAFF_MONTHLY_MEETING_DESCRIPTION", "Monthly staff meeting.")
STAFF_MONTHLY_MEETING_LOCATION = os.getenv("STAFF_MONTHLY_MEETING_LOCATION", "")
STAFF_EVENT_ICS_DOMAIN = os.getenv("STAFF_EVENT_ICS_DOMAIN", "rice-westnile.local")

# Social-platform API configuration.
# Keep all secrets in environment variables or the deployment secret manager.
# Do not commit access tokens, API keys, or client secrets to source control.
SOCIAL_MEDIA_SYNC_ENABLED = os.getenv("SOCIAL_MEDIA_SYNC_ENABLED", "False").lower() == "true"
SOCIAL_MEDIA_SYNC_INTERVAL_MINUTES = int(os.getenv("SOCIAL_MEDIA_SYNC_INTERVAL_MINUTES", "30"))
SOCIAL_MEDIA_API_TIMEOUT_SECONDS = int(os.getenv("SOCIAL_MEDIA_API_TIMEOUT_SECONDS", "30"))
SOCIAL_MEDIA_API_CONFIG = {
    "twitter": {
        "enabled": os.getenv("SOCIAL_TWITTER_ENABLED", "False").lower() == "true",
        "api_key": os.getenv("SOCIAL_TWITTER_API_KEY", ""),
        "api_secret": os.getenv("SOCIAL_TWITTER_API_SECRET", ""),
        "access_token": os.getenv("SOCIAL_TWITTER_ACCESS_TOKEN", ""),
        "access_token_secret": os.getenv("SOCIAL_TWITTER_ACCESS_TOKEN_SECRET", ""),
        "bearer_token": os.getenv("SOCIAL_TWITTER_BEARER_TOKEN", ""),
        "account_id": os.getenv("SOCIAL_TWITTER_ACCOUNT_ID", ""),
        "api_version": os.getenv("SOCIAL_TWITTER_API_VERSION", "2"),
    },
    "facebook": {
        "enabled": os.getenv("SOCIAL_FACEBOOK_ENABLED", "False").lower() == "true",
        "access_token": os.getenv("SOCIAL_FACEBOOK_ACCESS_TOKEN", ""),
        "page_id": os.getenv("SOCIAL_FACEBOOK_PAGE_ID", ""),
        "api_version": os.getenv("SOCIAL_FACEBOOK_API_VERSION", "v22.0"),
    },
    "instagram": {
        "enabled": os.getenv("SOCIAL_INSTAGRAM_ENABLED", "False").lower() == "true",
        "access_token": os.getenv("SOCIAL_INSTAGRAM_ACCESS_TOKEN", ""),
        "account_id": os.getenv("SOCIAL_INSTAGRAM_ACCOUNT_ID", ""),
        "api_version": os.getenv("SOCIAL_INSTAGRAM_API_VERSION", "v22.0"),
    },
    "linkedin": {
        "enabled": os.getenv("SOCIAL_LINKEDIN_ENABLED", "False").lower() == "true",
        "access_token": os.getenv("SOCIAL_LINKEDIN_ACCESS_TOKEN", ""),
        "organization_id": os.getenv("SOCIAL_LINKEDIN_ORGANIZATION_ID", "145215816"),
        "api_version": os.getenv("SOCIAL_LINKEDIN_API_VERSION", "202601"),
    },
    "youtube": {
        "enabled": os.getenv("SOCIAL_YOUTUBE_ENABLED", "False").lower() == "true",
        "api_key": os.getenv("SOCIAL_YOUTUBE_API_KEY", ""),
        "channel_id": os.getenv("SOCIAL_YOUTUBE_CHANNEL_ID", ""),
        "api_version": os.getenv("SOCIAL_YOUTUBE_API_VERSION", "v3"),
    },
    "whatsapp": {
        "enabled": os.getenv("SOCIAL_WHATSAPP_ENABLED", "False").lower() == "true",
        "access_token": os.getenv("SOCIAL_WHATSAPP_ACCESS_TOKEN", ""),
        "phone_number_id": os.getenv("SOCIAL_WHATSAPP_PHONE_NUMBER_ID", ""),
        "business_account_id": os.getenv("SOCIAL_WHATSAPP_BUSINESS_ACCOUNT_ID", ""),
        "api_version": os.getenv("SOCIAL_WHATSAPP_API_VERSION", "v22.0"),
    },
}

DEFAULT_DISPLAY_CURRENCY = os.getenv("DEFAULT_DISPLAY_CURRENCY", "UGX")

CACHES = {
    "default": {
        "BACKEND": os.getenv(
            "CACHE_BACKEND",
            "django.core.cache.backends.locmem.LocMemCache",
        ),
        "LOCATION": os.getenv("CACHE_LOCATION", "enterprise-cache"),
        "TIMEOUT": int(os.getenv("CACHE_TIMEOUT", "300")),
    }
}

if CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache":
    CACHES["default"]["OPTIONS"] = {
        "MAX_ENTRIES": int(os.getenv("CACHE_MAX_ENTRIES", "10000")),
    }

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", default=True)

# Compress HTML/CSS/JS responses when the web server has not already done so.
MIDDLEWARE.insert(1, "django.middleware.gzip.GZipMiddleware")
