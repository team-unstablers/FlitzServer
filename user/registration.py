from typing import TypedDict, NotRequired, Optional


class UserRegistrationContext(TypedDict):
    session_id: str

    device_info: str
    apns_token: Optional[str]

    country_code: str
    agree_marketing_notifications: bool

    phone_verification_state: Optional[dict]
    phone_number: Optional[str]

    phone_number_duplicated: bool


