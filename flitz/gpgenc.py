import os
import tempfile
from typing import Optional
import gnupg
from django.conf import settings
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile


def gpg_encrypt(content: bytes, pubkey_file: str) -> bytes:
    """
    주어진 내용을 GPG 공개키로 암호화합니다.

    :param content: 암호화할 내용 (바이트 문자열)
    :param pubkey_file: 공개키 파일 경로
    :returns: 암호화된 내용 (바이트 문자열)
    """
    # GPG 홈 디렉토리 설정 (임시 디렉토리 사용)
    with tempfile.TemporaryDirectory() as temp_gnupghome:
        gpg = gnupg.GPG(gnupghome=temp_gnupghome)
        
        # 공개키 임포트
        with open(pubkey_file, 'r') as f:
            import_result = gpg.import_keys(f.read())
            if not import_result.fingerprints:
                raise ValueError(f"Failed to import public key from {pubkey_file}")
        
        # 첫 번째 키의 fingerprint 사용
        fingerprint = import_result.fingerprints[0]
        
        # 암호화
        encrypted = gpg.encrypt(
            content,
            fingerprint,
            armor=True,  # ASCII armor 형식으로 출력
            always_trust=True  # 공개키를 신뢰
        )
        
        if not encrypted.ok:
            raise ValueError(f"Encryption failed: {encrypted.status}")
        
        return str(encrypted).encode('utf-8')


def get_gpg_key_fingerprint(pubkey_file: str) -> str:
    """
    GPG 공개키 파일로부터 fingerprint를 추출합니다.

    :param pubkey_file: 공개키 파일 경로
    :returns: 키의 fingerprint
    """
    with tempfile.TemporaryDirectory() as temp_gnupghome:
        gpg = gnupg.GPG(gnupghome=temp_gnupghome)
        
        with open(pubkey_file, 'r') as f:
            import_result = gpg.import_keys(f.read())
            if not import_result.fingerprints:
                raise ValueError(f"Failed to import public key from {pubkey_file}")
        
        return import_result.fingerprints[0]