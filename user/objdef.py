from typing import List, Optional, TypedDict, Literal, Dict

from enum import Enum
from dataclasses import dataclass, asdict

@dataclass
class UserProfile:
    hashtags: List[str]
    description: str



    @staticmethod
    def create_empty() -> "UserProfile":
        return UserProfile(
            hashtags=[]
        )

    def as_dict(self) -> dict:
        return asdict(self)

    def sanity_check(self):
        return True
