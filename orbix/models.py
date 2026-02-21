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


@dataclass(frozen=True, slots=True)
class UserBadge:
    id: int
    name: str
    description: str
    enabled: bool
    icon_image_id: int
    created: datetime | None
    awarded_count: int
    win_rate_percentage: float


@dataclass(frozen=True, slots=True)
class UserPresence:
    user_id: int
    presence_type: int
    last_location: str
    place_id: int | None
    root_place_id: int | None
    game_id: int | None
    universe_id: int | None


@dataclass(frozen=True, slots=True)
class Game:
    id: int
    root_place_id: int
    name: str
    description: str
    creator_id: int
    creator_name: str
    creator_type: str
    playing: int
    visits: int
    max_players: int
    created: datetime | None
    genre: str


@dataclass(frozen=True, slots=True)
class FavouriteGame:
    game: Game


@dataclass(frozen=True, slots=True)
class WearingItem:
    asset_id: int


@dataclass(frozen=True, slots=True)
class LimitedItem:
    user_asset_id: int
    serial_number: int
    asset_id: int
    name: str
    recent_average_price: int
    original_price: int
    asset_stock: int
    is_on_hold: bool
