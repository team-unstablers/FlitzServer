from django.urls import include, path
from rest_framework.routers import DefaultRouter

from safety.views import UserBlockViewSet

router = DefaultRouter()
router.register(r'blocks', UserBlockViewSet, basename='user-block')

urlpatterns = [
    path('', include(router.urls)),
]
