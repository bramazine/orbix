from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class UserProfile:
    id: int
    username: str
    display_name: str
    description: str
    created_date: datetime | None
    follower_count: int
    following_count: int
    friend_count: int
    is_verified: bool

    @property
    def profile_url(self) -> str:
        return f"https://www.roblox.com/users/{self.id}/profile"


@dataclass(frozen=True, slots=True)
class UserAvatar:
    user_id: int
    headshot_url: str
    bust_url: str
    full_body_url: str
