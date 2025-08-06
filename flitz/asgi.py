"""
ASGI config for flitz project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import messaging.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flitz.settings_dev')

app_asgi = get_asgi_application()

application = ProtocolTypeRouter({
    "http": app_asgi,
    "websocket": URLRouter(messaging.routing.websocket_urlpatterns),
})
