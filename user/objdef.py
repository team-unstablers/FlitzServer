from typing import List, Optional, TypedDict, Literal, Dict

from enum import Enum
from dataclasses import dataclass, asdict

class DeletedUserArchiveData(TypedDict):
    """
    삭제된 사용자 아카이브 정보
    """
    id: str

    username: Optional[str]
    display_name: Optional[str]
    email: Optional[str]
    phone_number: Optional[str]
    nice_di: Optional[str]