"""
Configuration Django de Ruche RH — logiciel de gestion RH multi-entreprises (Bénin).
"""

from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

DEV_SECRET_KEY = "django-insecure-dev-only-change-me"
SECRET_KEY = config("SECRET_KEY", default=DEV_SECRET_KEY)
DEBUG = config("DEBUG", default=True, cast=bool)
if not DEBUG and SECRET_KEY in (DEV_SECRET_KEY, "change-me", ""):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Définissez une SECRET_KEY secrète dans .env avant de passer DEBUG=False.")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps du projet
    "companies",
    "accounts",
    "employees",
    "attendance",
    "leaves",
    "payroll",
    "recruitment",
    "evaluations",
    "documents",
    "notifications",
    "explanations",
    "assets",
    "meetings",
    "biometrics",
    "expenses",
    "training",
    "discipline",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de données : SQLite en dev, PostgreSQL si DB_NAME est renseigné
if config("DB_NAME", default=""):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER", default=""),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Identité du produit (modifiable ici : nom affiché partout dans l'interface)
APP_NAME = config("APP_NAME", default="Ruche RH")
APP_TAGLINE = config("APP_TAGLINE", default="Gestion RH & pointage facial")

# Pointage facial
# Distance euclidienne maximale entre deux empreintes pour accepter une reconnaissance
# (plus petit = plus strict ; 0.6 est la valeur usuelle de face-api.js).
FACE_MATCH_THRESHOLD = config("FACE_MATCH_THRESHOLD", default=0.5, cast=float)
# Délai minimal entre deux pointages d'un même employé (évite les doubles passages)
ATTENDANCE_MIN_INTERVAL_MINUTES = config("ATTENDANCE_MIN_INTERVAL_MINUTES", default=2, cast=int)

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Fichiers confidentiels (CV, documents RH) : jamais servis directement, uniquement via des vues protégées.
PRIVATE_ROOT = BASE_DIR / "private"
UPLOAD_MAX_MB = 5

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# --------------------------------------------------------------- Production
# Active automatiquement quand DEBUG=False (HTTPS obligatoire : la caméra du navigateur l'exige).
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_AGE = config("SESSION_COOKIE_AGE", default=60 * 60 * 12, cast=int)  # 12 h

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": config("LOG_LEVEL", default="INFO")},
}

# ---------------------------------------------------------------- E-mails
# Sans configuration SMTP, les e-mails s'affichent dans la console (aucun envoi réel).
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="Ruche RH <no-reply@localhost>")
# Adresse publique (https://rh.mon-domaine.bj) ajoutée aux liens des e-mails
SITE_URL = config("SITE_URL", default="").rstrip("/")

# ------------------------------------------------- Empreinte digitale (WebAuthn)
# Par défaut, le domaine est déduit de la requête ; à fixer derrière certains proxys.
WEBAUTHN_RP_ID = config("WEBAUTHN_RP_ID", default="")
WEBAUTHN_ORIGIN = config("WEBAUTHN_ORIGIN", default="")
