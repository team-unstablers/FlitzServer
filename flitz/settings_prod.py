"""
Development environment settings for Flitz project.
"""
from .settings_base import *

SECRET_KEY = os.environ.get('FLITZ_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
DEVELOPMENT_MODE = False

ALLOWED_HOSTS = ['*']

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
    'drf_orjson_renderer.renderers.ORJSONRenderer',
]

STORAGES = {
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ.get('FLITZ_STATIC_BUCKET_NAME'),
            "endpoint_url": os.environ.get('FLITZ_S3_ENDPOINT_URL'),
            "access_key": os.environ.get('FLITZ_S3_ACCESS_KEY_ID'),
            "secret_key": os.environ.get('FLITZ_S3_SECRET_ACCESS_KEY'),
            "region_name": os.environ.get('FLITZ_S3_REGION_NAME'),
        }
    },
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ.get('FLITZ_CONTENT_BUCKET_NAME'),
            "endpoint_url": os.environ.get('FLITZ_S3_ENDPOINT_URL'),
            "access_key": os.environ.get('FLITZ_S3_ACCESS_KEY_ID'),
            "secret_key": os.environ.get('FLITZ_S3_SECRET_ACCESS_KEY'),
            "region_name": os.environ.get('FLITZ_S3_REGION_NAME'),
        }
    }

}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('FLITZ_REDIS_CACHE_URL'),
    }
}

# Celery Configuration for development
CELERY_BROKER_URL = os.environ.get('FLITZ_REDIS_CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = os.environ.get('FLITZ_REDIS_CELERY_BACKEND_URL')

# Channel Layers for development
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [{
                'address': os.environ.get('FLITZ_REDIS_CHANNEL_LAYER_URL'),
            }],
            'capacity': 1500,
            'expiry': 10,
        },
    },
}

# APNS Configuration for development
APNS_USE_SANDBOX = False

PHONE_NUMBER_HASH_SALT = os.environ.get('FLITZ_PHONE_NUMBER_HASH_SALT')

GPG_PUBLIC_KEY_FILE = 'flitz-prod.public.asc'
