from django.conf import settings

from hashlib import sha256


def hash_phone_number(phone_number: str) -> str:
    """Hash a phone number using a salted SHA-256 hash"""
    salt = settings.PHONE_NUMBER_HASH_SALT
    return sha256((salt + phone_number).encode()).hexdigest()
