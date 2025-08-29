from typing import TypedDict, NotRequired, Optional, Tuple

import base64
import json
import secrets

from datetime import date

from django.conf import settings

from safety.utils.phone_number import normalize_phone_number
from user.verification.errors import AdultVerificationError
from user.verification.kr.niceapi import NiceAPI, NiceAuthRequest, NiceEasyContext


class StartPhoneVerificationArgs(TypedDict):
    country_code: str

    phone_number: NotRequired[str]
    userdata: NotRequired[dict]


class StartPhoneVerificationResponse(TypedDict):
    is_success: bool
    additional_data: NotRequired[dict]

StartPhoneVerificationPrivateData = dict

class CompletePhoneVerificationArgs(TypedDict):
    country_code: str

    verification_code: NotRequired[str]

    encrypted_payload: NotRequired[str]
    payload_hmac: NotRequired[str]

class CompletePhoneVerificationResponse(TypedDict):
    phone_number: str
    additional_data: NotRequired[dict]

def is_adult(birth_date: date, country_code: str) -> bool:
    """
    주어진 생년월일과 국가 코드를 바탕으로 성인 여부를 판단합니다.
    """
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    if country_code == 'KR':
        return age >= 19
    else:
        return age >= 18

def start_phone_verification(args: StartPhoneVerificationArgs) -> Tuple[StartPhoneVerificationResponse, Optional[StartPhoneVerificationPrivateData]]:
    """
    전화번호 인증을 시작한다
    """

    country_code = args.get('country_code')

    if country_code == 'KR':
        # 대한민국의 경우 NICE 인증 API를 사용한다
        return start_phone_verification_kr(args)

    raise NotImplementedError("Flitz currently supports only KR phone verification.")

def start_phone_verification_kr(args: StartPhoneVerificationArgs) -> Tuple[StartPhoneVerificationResponse, Optional[StartPhoneVerificationPrivateData]]:
    """
    한국 전화번호 인증을 시작합니다
    """

    niceapi = NiceAPI.shared()

    nonce = f'FLITZ_USR_{secrets.token_urlsafe(12)}'

    userdata_dict = args.get('userdata', {})
    userdata = base64.b64encode(json.dumps(userdata_dict).encode()).decode()

    niceapi_context = niceapi.crypto_easy_cached_start()

    auth_request = NiceAuthRequest(
        requestno=nonce,
        returnurl=f'flitz://register/phone-verification/kr/callback',
        sitecode=niceapi_context['site_code'],
        authtype='M',
        methodtype='get',
        popupyn='N',
        receivedata=userdata
    )

    nice_payload, nice_hmac = niceapi.crypto_easy_encrypt(niceapi_context, auth_request)

    response: StartPhoneVerificationResponse = {
        'is_success': True,
        'additional_data': {
            'nice_payload': nice_payload,
            'nice_hmac': nice_hmac,
            'nice_token_version_id': niceapi_context['token_version_id']
        }
    }

    private_data = {
        'nonce': nonce,

        # 복구해서 사용해야 함, 왜냐하면 시간차로 토큰 값 / 암호화 키가 바뀔 수 있기 때문
        'nice_context': niceapi_context
    }

    return response, private_data

def complete_phone_verification(args: CompletePhoneVerificationArgs, private_data: Optional[dict]) -> CompletePhoneVerificationResponse:
    """
    전화번호 인증을 완료합니다
    """

    country_code = args.get('country_code')

    if country_code == 'KR':
        return complete_phone_verification_kr(args, private_data)

    raise NotImplementedError("Flitz currently supports only KR phone verification.")

def complete_phone_verification_kr(args: CompletePhoneVerificationArgs, private_data: Optional[dict]) -> CompletePhoneVerificationResponse:
    """
    한국 전화번호 인증을 완료합니다
    """

    # requires payload
    encrypted_payload = args.get('encrypted_payload')
    if encrypted_payload is None:
        raise ValueError("KR phone verification requires payload.")

    payload_hmac = args.get('payload_hmac')
    if payload_hmac is None:
        raise ValueError("KR phone verification requires payload HMAC.")

    # requires private data, especially niceapi context
    if private_data is None or 'nonce' not in private_data or 'nice_context' not in private_data:
        raise ValueError("KR phone verification requires private data.")

    niceapi = NiceAPI.shared()

    nonce: str = private_data['nonce']
    niceapi_context: NiceEasyContext = private_data['nice_context']

    response = niceapi.crypto_easy_decrypt(niceapi_context, encrypted_payload, payload_hmac, nonce)

    if response['resultcode'] != '0000':
        raise ValueError(f"KR phone verification failed with code {response['resultcode']}.")

    phone_number_raw = response['mobileno']
    birth_date_raw = response.get('birthdate')
    ci = response.get('ci')

    # parse date (YYYYMMDD -> date)
    year = int(birth_date_raw[0:4])
    month = int(birth_date_raw[4:6])
    day = int(birth_date_raw[6:8])

    birth_date = date.fromisoformat(f"{year:04d}-{month:02d}-{day:02d}")

    # normalize phone number
    phone_number = normalize_phone_number(phone_number_raw, 'KR')

    if not is_adult(birth_date, 'KR'):
        raise AdultVerificationError()

    return {
        'phone_number': phone_number,
        'additional_data': {
            'birth_date': birth_date,
            'ci': ci,
        }
    }
