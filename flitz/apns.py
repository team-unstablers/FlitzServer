from django.conf import settings

from typing import List, Optional
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

APNS_GLOBAL_IDENTITY: Optional[APNSIdentity] = None

def apns_default_identity() -> APNSIdentity:
    global APNS_GLOBAL_IDENTITY

    if APNS_GLOBAL_IDENTITY is None:
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



class APNS:
    PROD_URL = "https://api.push.apple.com/3/device/"
    DEV_URL = "https://api.development.push.apple.com/3/device/"

    identity: APNSIdentity
    sandbox: bool

    base_url: str

    def __init__(self, identity: APNSIdentity = apns_default_identity(), sandbox: bool=False):
        self.identity = identity
        self.sandbox = sandbox

        self.base_url = self.DEV_URL if sandbox else self.PROD_URL

    def send_push(self, title: str, body: str, device_tokens: List[str]):
        jwt = self.identity.jwt_token()

        data = {
            "aps": {
                "alert": {
                    "title": title,
                    "body": body
                }
            }
        }
        headers = {
            "authorization": "bearer " + jwt,
            "apns-topic": self.identity.bundle_id,
            "apns-push-type": "alert",
            "apns-priority": "10",
            "apns-expiration": "0"
        }
        
        with httpx.Client(http2=True) as client:
            for token in device_tokens:
                client.post(self.base_url + token, json=data, headers=headers)
