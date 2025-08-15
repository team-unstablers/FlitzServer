import jwt

from datetime import datetime, timezone

from django.conf import settings

from rest_framework import authentication

from user.models import User
from user_auth.models import UserSession

class UserSessionAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        if 'Authorization' not in request.headers:
            return None

        auth_header = request.headers['Authorization']
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[7:]

        try:
            jwt_payload = jwt.decode(token, key= settings.SECRET_KEY, algorithms=['HS256'])
            session_id = jwt_payload['sub']

            session: UserSession = UserSession.objects.select_related('user').filter(id=session_id).first()

            if session is None or session.invalidated_at is not None:
                return None

            if session.expires_at is not None:
                if session.expires_at < datetime.now(tz=timezone.utc):
                    return None

            try:
                session.user.update_last_seen()
            except Exception as e:
                # Log the error or handle it as needed
                print(f"Error updating last seen for user {session.user.id}: {e}")

            return session.user, session

        except jwt.InvalidTokenError:
            return None