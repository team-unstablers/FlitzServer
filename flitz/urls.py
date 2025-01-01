"""
URL configuration for flitz project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt

from rest_framework import routers

from messaging.views import DirectMessageConversationViewSet, DirectMessageViewSet, DirectMessageAttachmentViewSet
from user.views import PublicUserViewSet
from user_auth.views import request_token

from card.views import PublicCardViewSet, ReceivedCardViewSet, CardDistributionViewSet

from location.views import FlitzWaveViewSet

router = routers.DefaultRouter()

router.register(r'users', PublicUserViewSet, basename='User')
router.register(r'conversation/(?P<conversation_id>[0-9a-fA-F\-]+)/message', DirectMessageViewSet, basename='DirectMessage')
router.register(r'conversation/(?P<conversation_id>[0-9a-fA-F\-]+)/attachments', DirectMessageAttachmentViewSet, basename='DirectMessage')
router.register(r'conversation', DirectMessageConversationViewSet, basename='DirectMessageConversation')

router.register(r'wave', FlitzWaveViewSet, basename='FlitzWave')

router.register(r'cards/distributed', CardDistributionViewSet, basename='DistributedCard')
router.register(r'cards/received', ReceivedCardViewSet, basename='ReceivedCard')
router.register(r'cards', PublicCardViewSet, basename='Card')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token', csrf_exempt(request_token)),
    path('admin/', admin.site.urls),
]
