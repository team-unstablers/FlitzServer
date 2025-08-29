import jwt

from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache

from rest_framework import authentication
from rest_framework.request import Request

from user.models import User
from user.registration import UserRegistrationContext
from user_auth.models import UserSession

class UserSessionAuthentication(authentication.BaseAuthentication):
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

            if token_options != '--with-love':
                # XXX: refresh token을 사용한 인증을 막는다
                return None

            session: UserSession = (UserSession.objects.filter(id=session_id,
                                                               invalidated_at__isnull=True,
                                                               user__disabled_at__isnull=True)
                                    .select_related('user', 'user__location')
                                    .first())

            if session is None:
                return None

            if session.expires_at is not None:
                if session.expires_at < datetime.now(tz=timezone.utc):
                    return None

            if not request.get_full_path().startswith('/wave/'):
                try:
                    session.user.update_last_seen()
                except Exception as e:
                    # Log the error or handle it as needed
                    print(f"Error updating last seen for user {session.user.id}: {e}")

            return session.user, session

        except jwt.InvalidTokenError:
            return None

class UserRegistrationSessionAuthentication(authentication.BaseAuthentication):
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

            if not ('--with-love' in token_options and '--registration' in token_options):
                return None

            context = UserRegistrationContext.load(session_id)

            if context is None:
                return None

            return context, None

        except jwt.InvalidTokenError:
            return None
