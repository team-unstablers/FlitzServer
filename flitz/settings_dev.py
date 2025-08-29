"""
Development environment settings for Flitz project.
"""
import os

from .settings_base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-9@s8#wqep7zu^ksyb0$mq#zw)zxjng+(2108!+=z(y1h-*v9wj'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

DEVELOPMENT_MODE = True

ALLOWED_HOSTS = ['*']

# Development specific settings
LOCALHOST = os.environ.get('FLITZ_HOSTNAME', 'cheese-mbpr14.local')

# Database for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': os.environ.get('FLITZ_DB_HOST', 'localhost'),
        'PORT': os.environ.get('FLITZ_DB_PORT', '5433'),
        'NAME': os.environ.get('FLITZ_DB_NAME', 'flitzdev'),
        'USER': os.environ.get('FLITZ_DB_USER', 'flitzdev'),
        'PASSWORD': os.environ.get('FLITZ_DB_PASSWORD', 'flitzdev123'),
    },
}

# REST Framework - Add browsable API for development
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# Storage settings for development (MinIO)
STORAGES = {
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": "flitz-server-static",
            "access_key": "flitzdev",
            "secret_key": "flitzdev123",
            "endpoint_url": f"http://{LOCALHOST}:9000"
        }
    },
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": "flitz",
            "access_key": "flitzdev",
            "secret_key": "flitzdev123",
            "endpoint_url": f"http://{LOCALHOST}:9000",
            "object_parameters": {
                "ACL": "public-read"
            },
        }
    }
}

# Celery Configuration for development
CELERY_BROKER_URL = 'redis://localhost:6380/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6380/0'

# Channel Layers for development
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('localhost', 6380)],
            'capacity': 1500,
            'expiry': 10,
        },
    },
}

# APNS Configuration for development
APNS_USE_SANDBOX = True

PHONE_NUMBER_HASH_SALT = 'd634]Asp+,!a?pzbp*V2LM4x%qDmbE#.'

GPG_PUBLIC_KEY_FILE = 'flitz-dev.public.asc'

SLACK_WEBHOOK_URL = os.environ.get('FLITZ_SLACK_WEBHOOK_URL')

MAILGUN_API_KEY = os.environ.get('FLITZ_MAILGUN_API_KEY')
MAILGUN_DOMAIN = os.environ.get('FLITZ_MAILGUN_DOMAIN')