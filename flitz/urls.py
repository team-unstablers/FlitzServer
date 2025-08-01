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
from django.conf import settings

from rest_framework import routers, permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from messaging.views import DirectMessageConversationViewSet, DirectMessageViewSet, DirectMessageAttachmentViewSet
from user.views import PublicUserViewSet
from user_auth.views import request_token

from card.views import PublicCardViewSet, ReceivedCardViewSet, CardDistributionViewSet

from location.views import FlitzWaveViewSet
from safety.views import UserBlockViewSet

schema_view = get_schema_view(
    openapi.Info(
        title="Flitz API",
        default_version='v1',
        description="Flitz - 남성 동성애자를 위한 데이팅 앱 서비스 API",
        terms_of_service="https://www.flitz.app/terms/",
        contact=openapi.Contact(email="support@flitz.app"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

router = routers.DefaultRouter()

router.register(r'users', PublicUserViewSet, basename='User')
router.register(r'conversation/(?P<conversation_id>[0-9a-fA-F\-]+)/message', DirectMessageViewSet, basename='DirectMessage')
router.register(r'conversation/(?P<conversation_id>[0-9a-fA-F\-]+)/attachments', DirectMessageAttachmentViewSet, basename='DirectMessageAttachments')
router.register(r'conversation', DirectMessageConversationViewSet, basename='DirectMessageConversation')

router.register(r'wave', FlitzWaveViewSet, basename='FlitzWave')

router.register(r'cards/distribution', CardDistributionViewSet, basename='CardDistribution')
# router.register(r'cards/received', ReceivedCardViewSet, basename='ReceivedCard')
router.register(r'cards', PublicCardViewSet, basename='Card')
router.register(r'blocks', UserBlockViewSet, basename='UserBlock')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token', csrf_exempt(request_token)),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += [
        # API Documentation (only in DEBUG mode)
        path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
        path('swagger.yaml', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    ]
