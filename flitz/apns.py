from typing import List
import requests
import jwt
import time

class APNS:
    ALGORITHM = 'ES256'
    PROD_URL = "https://api.push.apple.com/3/device/"
    DEV_URL = "https://api.development.push.apple.com/3/device/"
    
    def __init__(self, key_file, team_id, key_id, bundle_id, sandbox=False):
        self.key_file = key_file
        self.team_id = team_id
        self.key_id = key_id
        self.bundle_id = bundle_id
        self.sandbox = sandbox
        self.base_url = self.DEV_URL if sandbox else self.PROD_URL
        self.jwt = self._generate_token()
    
    def _generate_token(self) -> str:
        with open(self.key_file, 'r') as f:
            private_key = f.read()
            
        token = jwt.encode(
            {
                'iss': self.team_id,
                'iat': time.time()
            },
            private_key,
            algorithm=self.ALGORITHM,
            headers={
                'alg': self.ALGORITHM,
                'kid': self.key_id
            }
        )
        return token
    
    def send_push(self, title: str, body: str, device_tokens: List[str]):
        data = {
            "aps": {
                "alert": {
                    "title": title,
                    "body": body
                }
            }
        }
        headers = {
            "authorization": "bearer " + self.jwt,
            "apns-topic": self.bundle_id,
            "apns-push-type": "alert",
            "apns-priority": "10",
            "apns-expiration": "0"
        }
        
        for token in device_tokens:
            requests.post(self.base_url + token, json=data, headers=headers)
