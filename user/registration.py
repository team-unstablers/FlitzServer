from dataclasses import dataclass, asdict
from typing import TypedDict, NotRequired, Optional

from dacite import from_dict
from django.core.cache import cache


@dataclass
class UserRegistrationContext:
    session_id: str

    device_info: str
    apns_token: Optional[str]

    country_code: str
    agree_marketing_notifications: bool

    phone_verification_state: Optional[dict]
    phone_number: Optional[str]
    phone_verification_additional_data: Optional[dict]

    phone_number_duplicated: bool

    @property
    def is_authenticated(self) -> bool:
        """
        DRF 호환용
        """
        return True

    @staticmethod
    def load(session_id: str) -> Optional["UserRegistrationContext"]:
        data = cache.get(f"fz:user_registration:{session_id}")
        if data is None:
            return None

        return from_dict(UserRegistrationContext, data)

    def as_dict(self) -> dict:
        return asdict(self)

    def save(self):
        cache.set(f"fz:user_registration:{self.session_id}", self.as_dict(), timeout=15 * 30)



