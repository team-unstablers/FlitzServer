from typing import TypedDict, Optional

import json

from django.http import HttpResponse
from django.http.request import HttpRequest

from user.models import User

from user_auth.models import UserSession

# Create your views here.

class TokenRequestPayload(TypedDict):
    username: str
    password: str

    device_info: Optional[str]

def request_token(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        payload: TokenRequestPayload = json.loads(request.body)

        user = User.objects.get(username=payload['username'])

        if not user.check_password(payload['password']):
            return HttpResponse(status=401)

        payload.setdefault('device_info', 'unknown')
        # create session
        session = UserSession.objects.create(
            user=user,
            description=payload['device_info'],
            initiated_from=request.META.get('REMOTE_ADDR'),
        )

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


def create_user(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload: TokenRequestPayload = json.loads(request.body)

        user = User.objects.create(
            username=payload['username'],
            password=payload['password'],
        )

        return HttpResponse(status=201)
    except Exception as e:
        pass
        return HttpResponse(status=400)


