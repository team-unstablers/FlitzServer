def validate_password(password: str) -> (bool, str):
    """
    비밀번호 유효성 검사 함수
    :param password: 검사할 비밀번호 문자열
    :return: (유효성 여부, 오류 메시지)
    """

    if len(password) < 8:
        return False, "비밀번호는 최소 8자 이상이어야 합니다."

    if not any(char.isdigit() for char in password):
        return False, "비밀번호에는 숫자가 포함되어야 합니다."

    if not any(char in "!@#$%^&*()-_=+[]{}|;:,.<>?/" for char in password):
        return False, "비밀번호에는 특수문자가 포함되어야 합니다."

    return True, ""