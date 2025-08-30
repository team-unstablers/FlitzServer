from django.conf import settings

import phonenumbers
from hashlib import sha256
from typing import Optional


def normalize_phone_number(phone_number: str, region: Optional[str] = None) -> str:
    """
    Normalize a phone number to E.164 format (e.g. +821012345678).
    
    Args:
        phone_number: The phone number to normalize.
        region: The region/country code to use for parsing. If not provided, 
                the phone number should include a country code.
    
    Returns:
        The normalized phone number in E.164 format.
        
    Raises:
        phonenumbers.NumberParseException: If the phone number is invalid or cannot be parsed.
    """
    try:
        # Parse the phone number with the given region
        parsed = phonenumbers.parse(phone_number, region)
        
        # Check if the number is valid
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        
        # Format in E.164 format
        normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return normalized
    except phonenumbers.NumberParseException as e:
        # Re-raise the exception to inform the caller about the specific parsing issue
        raise e

def to_local_phone_number(phone_number: str, region: str = 'KR') -> str:
    """
    Convert a phone number to local format (e.g. 010-1234-5678 for South Korea).

    Args:
        phone_number: The phone number to convert.
        region: The region/country code to use for parsing. Default is 'KR' (South Korea).

    Returns:
        The phone number in local format.

    Raises:
        phonenumbers.NumberParseException: If the phone number is invalid or cannot be parsed.
    """
    try:
        # Parse the phone number with the given region
        parsed = phonenumbers.parse(phone_number, region)

        # Check if the number is valid
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")

        # Format in national (local) format
        local_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        return local_number
    except phonenumbers.NumberParseException as e:
        # Re-raise the exception to inform the caller about the specific parsing issue
        raise e


def hash_phone_number(phone_number: str) -> str:
    """Hash a phone number using a salted SHA-256 hash"""
    salt = settings.PHONE_NUMBER_HASH_SALT
    return sha256((salt + phone_number).encode()).hexdigest()
