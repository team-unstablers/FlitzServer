from typing import List, Optional

import os

from django.conf import settings

import httpx
import jwt
import time

class APNSIdentity:
    private_key: str
    team_id: str
    key_id: str
    bundle_id: str

    def __init__(self, private_key: str, team_id: str, key_id: str, bundle_id: str):
        self.private_key = private_key
        self.team_id = team_id
        self.key_id = key_id
        self.bundle_id = bundle_id

    def jwt_token(self, algorithm: str = 'ES256') -> str:
        token = jwt.encode(
            {
                'iss': self.team_id,
                'iat': time.time()
            },
            self.private_key,
            algorithm=algorithm,
            headers={
                'alg': algorithm,
                'kid': self.key_id
            }
        )

        return token

class MockedAPNSIdentity(APNSIdentity):
    """
    아, 어쨌든 이건 APNSIdentity라구요!
    """

    def __init__(self):
        super().__init__('', '', '', '')

    def jwt_token(self, algorithm: str = 'ES256') -> str:
        return "mocked_token"


APNS_GLOBAL_IDENTITY: Optional[APNSIdentity] = None

def apns_default_identity() -> APNSIdentity:
    global APNS_GLOBAL_IDENTITY

    if APNS_GLOBAL_IDENTITY is None:

        # 테스트 환경에서는 모킹된 인증 정보 사용
        if os.environ.get('FLITZ_TEST', '0') == '1':
            return MockedAPNSIdentity()

        key_file = settings.APNS_KEY_FILE
        team_id = settings.APNS_TEAM_ID
        key_id = settings.APNS_KEY_ID
        bundle_id = settings.APNS_BUNDLE_ID

        with open(key_file, 'r') as f:
            private_key = f.read()

        APNS_GLOBAL_IDENTITY = APNSIdentity(
            private_key=private_key,
            team_id=team_id,
            key_id=key_id,
            bundle_id=bundle_id
        )

    return APNS_GLOBAL_IDENTITY


APNS_GLOBAL_INSTANCE: Optional['APNS'] = None

class MockedAPNS:
    """
    테스트 환경에서 사용할 모킹된 APNS 클래스
    실제로 푸시 알림을 보내지 않고 로깅만 수행합니다.
    """
    def __init__(self, identity: APNSIdentity = None, sandbox: bool = False):
        if identity is None:
            identity = MockedAPNSIdentity()
        self.identity = identity
        self.sandbox = sandbox
        self.base_url = "https://mocked.push.apple.com/3/device/"  # 실제로 사용되지 않음
    
    def send_notification(self, title: str, body: str, device_tokens: List[str], user_info: dict=None):
        if user_info is None:
            payload = dict()
        else:
            payload = user_info.copy()

        payload['aps'] = {
            "alert": {
                "title": title,
                "body": body
            }
        }

        self.send_push(payload=payload, device_tokens=device_tokens)
    
    def send_push(self, payload: dict, device_tokens: List[str]):
        # 실제 HTTP 요청을 보내지 않고 로깅만 수행
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[MOCKED] Would send push notification: {payload} to {device_tokens}")
        # 실제 요청을 보내지 않음


class APNS:
    PROD_URL = "https://api.push.apple.com/3/device/"
    DEV_URL = "https://api.development.push.apple.com/3/device/"

    identity: APNSIdentity
    sandbox: bool

    base_url: str

    @staticmethod
    def default() -> 'APNS':
        global APNS_GLOBAL_INSTANCE

        if APNS_GLOBAL_INSTANCE is None:
            # 테스트 환경인지 확인
            if os.environ.get('FLITZ_TEST', '0') == '1':
                APNS_GLOBAL_INSTANCE = MockedAPNS(sandbox=settings.APNS_USE_SANDBOX)
            else:
                APNS_GLOBAL_INSTANCE = APNS(sandbox=settings.APNS_USE_SANDBOX)

        return APNS_GLOBAL_INSTANCE

    def __init__(self, identity: APNSIdentity = apns_default_identity(), sandbox: bool=False):
        self.identity = identity
        self.sandbox = sandbox

        self.base_url = self.DEV_URL if sandbox else self.PROD_URL

    def send_notification(self, title: str, body: str, device_tokens: List[str], user_info: dict=None):
        if user_info is None:
            payload = dict()
        else:
            payload = user_info.copy()

        payload['aps'] = {
            "alert": {
                "title": title,
                "body": body
            }
        }

        self.send_push(payload=payload, device_tokens=device_tokens)

    def send_push(self, payload: dict, device_tokens: List[str]):
        jwt_token = self.identity.jwt_token()

        headers = {
            "authorization": "bearer " + jwt_token,
            "apns-topic": self.identity.bundle_id,
            "apns-push-type": "alert",
            "apns-priority": "10",
            "apns-expiration": "0"
        }
        
        with httpx.Client(http2=True) as client:
            for token in device_tokens:
                client.post(self.base_url + token, json=payload, headers=headers)
