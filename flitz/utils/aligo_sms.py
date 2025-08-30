import threading

import requests
from django.conf import settings


class AligoSMS:
    base_url = 'https://apis.aligo.in'

    user_id: str
    api_key: str

    sender_number: str

    __shared__ = None
    __lock__ = threading.Lock()

    @classmethod
    def shared(cls) -> 'AligoSMS':
        if cls.__shared__ is None:
            with cls.__lock__:
                if cls.__shared__ is None:
                    instance = cls(
                        user_id=settings.ALIGO_USER_ID,
                        api_key=settings.ALIGO_API_KEY,
                        sender_number=settings.ALIGO_SENDER_NUMBER,
                    )

                    cls.__shared__ = instance

        return cls.__shared__

    def __init__(self, user_id: str, api_key: str, sender_number: str):
        self.user_id = user_id
        self.api_key = api_key

        self.sender_number = sender_number

    def send_lms(self, to: str, title: str, message: str) -> bool:
        response = requests.post(f'{self.base_url}/send/', data={
            'key': self.api_key,
            'user_id': self.user_id,
            'sender': self.sender_number,
            'receiver': to,

            'msg': message,
            'msg_type': 'LMS',
            'title': title
        })

        response.raise_for_status()

        body = response.json()
        print(body)
        return body['result_code'] == 1
