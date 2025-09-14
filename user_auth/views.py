import json

import jwt
import sentry_sdk
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.http.request import HttpRequest
from django.utils import timezone

from flitz.turnstile import validate_turnstile
from user.models import User
from user_auth.models import UserSession
from user_auth.serializers import TokenRequestSerializer, TokenRefreshRequestSerializer


# Create your views here.

@transaction.atomic
def request_token(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        data = json.loads(request.body)
        serializer = TokenRequestSerializer(data=data)
        if not serializer.is_valid():
            return HttpResponse(status=400)

        turnstile_token = serializer.validated_data['turnstile_token']
        remote_addr = request.META.get('REMOTE_ADDR')
        turnstile_response = validate_turnstile(turnstile_token) # TODO: remote_addr 전달

        if not turnstile_response['success']:
            print(f"turnstile failed: {turnstile_response}")
            return HttpResponse(status=401)

        if turnstile_response['action'] != 'request_token':
            print(f"turnstile action mismatch: {turnstile_response}")
            return HttpResponse(status=401)

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
        refresh_token = session.update_refresh_token()

        response_json = json.dumps({
            'token': token,
            'refresh_token': refresh_token
        }).encode()

        return HttpResponse(response_json, content_type='application/json', status=201)
    except Exception as e:
        # TODO: logging
        print(e)
        return HttpResponse(status=401)

@transaction.atomic
def refresh_token_view(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        data = json.loads(request.body)
        serializer = TokenRefreshRequestSerializer(data=data)
        if not serializer.is_valid():
            return HttpResponse(status=400)

        validated_data = serializer.validated_data

        refresh_token = validated_data['refresh_token']
        jwt_payload = jwt.decode(refresh_token, key=settings.SECRET_KEY, algorithms=['HS256'])

        token_options = jwt_payload.get('x-flitz-options', '')
        if ('--with-love' not in token_options) or ('--refresh' not in token_options):
            return HttpResponse(status=401)

        session_id = jwt_payload['sub']

        # refresh_token=refresh_token,
        session: UserSession = (UserSession.objects.filter(id=session_id,
                                                           invalidated_at__isnull=True,
                                                           user__disabled_at__isnull=True)
                                .select_related('user', 'user__location')
                                .first())

        if session is None:
            return HttpResponse(status=481)

        token = session.create_token()
        new_refresh_token = session.update_refresh_token()

        response_json = json.dumps({
            'token': token,
            'refresh_token': new_refresh_token
        }).encode()

        return HttpResponse(response_json, content_type='application/json', status=201)
    except jwt.InvalidTokenError:
        return HttpResponse(status=401)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return HttpResponse(status=500)

