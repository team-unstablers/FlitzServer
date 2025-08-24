import json

from django.db import transaction
from django.http import HttpResponse
from django.http.request import HttpRequest
from django.utils import timezone

from user.models import User
from user_auth.models import UserSession
from user_auth.serializers import TokenRequestSerializer, UserCreationSerializer

# Create your views here.

def request_token(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        data = json.loads(request.body)
        serializer = TokenRequestSerializer(data=data)
        if not serializer.is_valid():
            return HttpResponse(status=400)
        
        validated_data = serializer.validated_data

        try:
            user = User.objects.get(
                username=validated_data['username'],
                disabled_at__isnull=True,
            )
        except User.DoesNotExist:
            return HttpResponse(status=401)

        if not user.check_password(validated_data['password']):
            return HttpResponse(status=401)

        with transaction.atomic():
            # invalidate previous sessions
            UserSession.objects.filter(
                user=user, invalidated_at__isnull=True
            ).update(invalidated_at=timezone.now())

            # create session
            session = UserSession.objects.create(
                user=user,
                description=validated_data['device_info'],
                initiated_from=request.META.get('REMOTE_ADDR'),
                apns_token=validated_data.get('apns_token'),
            )

            user.primary_session = session
            user.save()

        # create token
        token = session.create_token()

        response_json = json.dumps({
            'token': token
        }).encode()

        return HttpResponse(response_json, content_type='application/json', status=201)
    except Exception as e:
        # TODO: logging
        print(e)
        return HttpResponse(status=401)

