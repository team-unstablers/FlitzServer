import jwt

from datetime import datetime, timezone

from django.conf import settings

from rest_framework import authentication
from rest_framework.request import Request

from wavespot.models import WaveSpotAppClipSession


class WaveSpotAppClipAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request: Request):
        if 'Authorization' not in request.headers:
            return None

        auth_header = request.headers['Authorization']
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[7:]

        try:
            jwt_payload = jwt.decode(token, key=settings.SECRET_KEY, algorithms=['HS256'])
            session_id = jwt_payload['sub']
            token_options = jwt_payload.get('x-flitz-options', '')

            if not ('--with-love' in token_options and '--wavespot-session' in token_options):
                # XXX: wavespot session을 사용한 인증이 아닌 경우는 거부한다
                return None

            session = WaveSpotAppClipSession.objects.filter(
                id=session_id,
                invalidated_at__isnull=True,
            ).first()

            if session is None:
                return None

            if session.expires_at is not None:
                if session.expires_at < datetime.now(tz=timezone.utc):
                    return None

            return session, None

        except jwt.InvalidTokenError:
            return None



