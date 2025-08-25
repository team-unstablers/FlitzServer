from typing import Optional, TypedDict, NotRequired

import requests

from django.conf import settings

TurnstileResponse = TypedDict('TurnstileResponse', {
    'success': bool,
    'challenge_ts': NotRequired[str],
    'hostname': NotRequired[str],
    'error-codes': NotRequired[list[str]],
    'action': NotRequired[str],
})

def validate_turnstile(token: str, remote_addr: Optional[str] = None) -> TurnstileResponse:
    url = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

    data = {
        'secret': settings.TURNSTILE_SECRET_KEY,
        'response': token,
    }

    if remote_addr:
        data['remoteip'] = remote_addr

    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # TODO: log to sentry
        return {'success': False, 'error-codes': ['internal-error']}


