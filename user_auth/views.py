import json

from django.http import HttpResponse
from django.http.request import HttpRequest

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
            user = User.objects.get(username=validated_data['username'])
        except User.DoesNotExist:
            return HttpResponse(status=401)

        if not user.check_password(validated_data['password']):
            return HttpResponse(status=401)

        # create session
        session = UserSession.objects.create(
            user=user,
            description=validated_data['device_info'],
            initiated_from=request.META.get('REMOTE_ADDR'),
            apns_token=validated_data.get('apns_token'),
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
        data = json.loads(request.body)
        serializer = UserCreationSerializer(data=data)
        if not serializer.is_valid():
            return HttpResponse(status=400)
        
        validated_data = serializer.validated_data

        user = User.objects.create(
            username=validated_data['username'],
        )
        user.set_password(validated_data['password'])
        user.save()

        return HttpResponse(status=201)
    except Exception as e:
        # TODO: logging
        print(e)
        return HttpResponse(status=400)
