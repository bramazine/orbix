from __future__ import annotations

import logging
from asyncio import gather
from dataclasses import replace
from datetime import datetime
from typing import Any, Self, cast

from .core import (
    HTTPClient,
    rate_limit,
    retry_on_failure,
)
from .exceptions import UserNotFoundError
from .models import (
    FavouriteGame,
    Game,
    LimitedItem,
    UserAvatar,
    UserBadge,
    UserPresence,
    UserProfile,
    WearingItem,
)

log = logging.getLogger(__name__)


class OrbixClient:
    def __init__(
        self,
        timeout: int = 30,
        cache_ttl: int = 300,
    ) -> None:
        self._http = HTTPClient(
            timeout=timeout,
            cache_ttl=cache_ttl,
        )

    async def close(self) -> None:
        await self._http.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    async def warm_cache(
        self,
        user_ids: list[int],
    ) -> None:
        if not user_ids:
            return

        chunk_size = 50
        tasks = [
            self.get_users_batch(
                user_ids[i : i + chunk_size]
            )
            for i in range(
                0, len(user_ids), chunk_size
            )
        ]

        await gather(
            *tasks, return_exceptions=True
        )

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user(
        self,
        user_id: int,
    ) -> UserProfile:
        response = await self._http.get(
            "users", f"/v1/users/{user_id}"
        )

        profile = self._parse_user_profile(
            response
        )

        try:
            results = await gather(
                self.get_user_follower_count(
                    user_id
                ),
                self.get_user_following_count(
                    user_id
                ),
                self.get_user_friend_count(
                    user_id
                ),
                return_exceptions=True,
            )

            counts = [
                cast("int", r)
                if not isinstance(r, Exception)
                else 0
                for r in results
            ]

            profile = replace(
                profile,
                follower_count=counts[0],
                following_count=counts[1],
                friend_count=counts[2],
            )
        except Exception:
            log.exception(
                "couldn't grab follower counts for user %d",
                user_id,
            )

        return profile

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_users_batch(
        self,
        user_ids: list[int],
    ) -> list[UserProfile]:
        if len(user_ids) > 100:
            raise ValueError(
                "batch limited to 100 users"
            )

        if not user_ids:
            return []

        response = await self._http.post(
            "users",
            "/v1/users",
            data={
                "userIds": user_ids,
                "excludeBannedUsers": True,
            },
        )

        return [
            self._parse_user_profile(ud)
            if "created" in ud
            else UserProfile(
                id=ud["id"],
                username=ud["name"],
                display_name=ud.get(
                    "displayName", ud["name"]
                ),
                description=ud.get(
                    "description", ""
                ),
                created_date=None,
                follower_count=0,
                following_count=0,
                friend_count=0,
                is_verified=ud.get(
                    "hasVerifiedBadge", False
                ),
            )
            for ud in response.get("data", [])
        ]

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_by_username(
        self,
        username: str,
    ) -> UserProfile:
        response = await self._http.post(
            "users",
            "/v1/usernames/users",
            data={
                "usernames": [username],
                "excludeBannedUsers": True,
            },
        )

        data = response.get("data")
        if not data:
            raise UserNotFoundError(username)

        return await self.get_user(data[0]["id"])

    @rate_limit(calls_per_minute=180)
    @retry_on_failure(max_retries=3)
    async def get_user_avatar(
        self,
        user_id: int,
        headshot_size: str = "48x48",
        bust_size: str = "48x48",
        full_body_size: str = "150x150",
    ) -> UserAvatar:
        results = await gather(
            self._http.get(
                "thumbnails",
                "/v1/users/avatar-headshot",
                params={
                    "userIds": str(user_id),
                    "size": headshot_size,
                    "format": "Png",
                },
            ),
            self._http.get(
                "thumbnails",
                "/v1/users/avatar-bust",
                params={
                    "userIds": str(user_id),
                    "size": bust_size,
                    "format": "Png",
                },
            ),
            self._http.get(
                "thumbnails",
                "/v1/users/avatar",
                params={
                    "userIds": str(user_id),
                    "size": full_body_size,
                    "format": "Png",
                },
            ),
            return_exceptions=True,
        )

        urls = [
            self._extract_thumbnail_url(
                cast(
                    "dict[str, Any]",
                    r
                    if not isinstance(
                        r, Exception
                    )
                    else {},
                )
            )
            for r in results
        ]

        return UserAvatar(
            user_id=user_id,
            headshot_url=urls[0],
            bust_url=urls[1],
            full_body_url=urls[2],
        )

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_followers(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[UserProfile]:
        response = await self._http.get(
            "friends",
            f"/v1/users/{user_id}/followers",
            params={
                "limit": min(limit, 100),
                "sortOrder": "Desc",
            },
        )

        return [
            self._parse_user_profile_simple(d)
            for d in response.get("data", [])
        ]

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_following(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[UserProfile]:
        response = await self._http.get(
            "friends",
            f"/v1/users/{user_id}/followings",
            params={
                "limit": min(limit, 100),
                "sortOrder": "Desc",
            },
        )

        return [
            self._parse_user_profile_simple(d)
            for d in response.get("data", [])
        ]

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_friends(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[UserProfile]:
        response = await self._http.get(
            "friends",
            f"/v1/users/{user_id}/friends",
            params={"limit": min(limit, 100)},
        )

        return [
            self._parse_user_profile_simple(d)
            for d in response.get("data", [])
        ]

    @rate_limit(calls_per_minute=60)
    @retry_on_failure(max_retries=3)
    async def get_user_follower_count(
        self,
        user_id: int,
    ) -> int:
        response = await self._http.get(
            "friends",
            f"/v1/users/{user_id}/followers/count",
        )
        return response.get("count", 0)

    @rate_limit(calls_per_minute=60)
    @retry_on_failure(max_retries=3)
    async def get_user_following_count(
        self,
        user_id: int,
    ) -> int:
        response = await self._http.get(
            "friends",
            f"/v1/users/{user_id}/followings/count",
        )
        return response.get("count", 0)

    @rate_limit(calls_per_minute=60)
    @retry_on_failure(max_retries=3)
    async def get_user_friend_count(
        self,
        user_id: int,
    ) -> int:
        response = await self._http.get(
            "friends",
            f"/v1/users/{user_id}/friends/count",
        )
        return response.get("count", 0)

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_badges(
        self,
        user_id: int,
        limit: int = 10,
        sort_order: str = "Asc",
        cursor: str | None = None,
    ) -> dict[str, Any]:
        allowed_limits = [10, 25, 50, 100]
        if limit not in allowed_limits:
            limit = min(
                allowed_limits,
                key=lambda x: abs(x - limit),
            )

        params = {
            "limit": limit,
            "sortOrder": sort_order,
        }

        if cursor:
            params["cursor"] = cursor

        response = await self._http.get(
            "badges",
            f"/v1/users/{user_id}/badges",
            params=params,
        )

        badges = []
        for badge_data in response.get(
            "data", []
        ):
            try:
                badges.append(
                    self._parse_user_badge(
                        badge_data
                    )
                )
            except Exception:
                log.exception(
                    "badge data looks wonky: %s",
                    badge_data,
                )
                continue

        return {
            "badges": badges,
            "previous_cursor": response.get(
                "previousPageCursor"
            ),
            "next_cursor": response.get(
                "nextPageCursor"
            ),
        }

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_presence(
        self,
        user_ids: list[int],
    ) -> list[UserPresence]:
        if not user_ids:
            return []

        if len(user_ids) > 20:
            raise ValueError(
                "20 user IDs allowed per request"
            )

        response = await self._http.post(
            "presence",
            "/v1/presence/users",
            data={"userIds": user_ids},
        )

        presences = []
        for presence_data in response.get(
            "userPresences", []
        ):
            try:
                presences.append(
                    self._parse_user_presence(
                        presence_data
                    )
                )
            except Exception:
                log.exception(
                    "presence data is messed up: %s",
                    presence_data,
                )
                continue

        return presences

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_presence_single(
        self,
        user_id: int,
    ) -> UserPresence | None:
        presences = await self.get_user_presence(
            [user_id]
        )
        return presences[0] if presences else None

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_favourite_games(
        self,
        user_id: int,
        limit: int = 10,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "limit": min(limit, 50),
            "sortOrder": "Desc",
        }

        if cursor:
            params["cursor"] = cursor

        try:
            response = await self._http.get(
                "games",
                f"/v2/users/{user_id}/favourite/games",
                params=params,
            )

            favourite_games = []
            for game_data in response.get(
                "data", []
            ):
                try:
                    game = self._parse_game_basic(
                        game_data
                    )
                    favourite_games.append(
                        FavouriteGame(game=game)
                    )
                except Exception:
                    log.exception(
                        "favourite game data is broken: %s",
                        game_data,
                    )
                    continue

            return {
                "favourite_games": favourite_games,
                "previous_cursor": response.get(
                    "previousPageCursor"
                ),
                "next_cursor": response.get(
                    "nextPageCursor"
                ),
            }
        except Exception as e:
            log.warning(
                "can't get favourite games for user %d: %s",
                user_id,
                e,
            )
            return {
                "favourite_games": [],
                "previous_cursor": None,
                "next_cursor": None,
            }

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_game_details(
        self,
        universe_ids: list[int],
    ) -> list[Game]:
        if not universe_ids:
            return []

        if len(universe_ids) > 100:
            raise ValueError(
                "100 universe IDs allowed per request"
            )

        params = {
            "universeIds": ",".join(
                map(str, universe_ids)
            )
        }

        response = await self._http.get(
            "games",
            "/v1/games",
            params=params,
        )

        games = []
        for game_data in response.get("data", []):
            try:
                games.append(
                    self._parse_game_detailed(
                        game_data
                    )
                )
            except Exception:
                log.exception(
                    "game data is messed up: %s",
                    game_data,
                )
                continue

        return games

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_game_details_single(
        self,
        universe_id: int,
    ) -> Game | None:
        games = await self.get_game_details(
            [universe_id]
        )
        return games[0] if games else None

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_currently_wearing(
        self,
        user_id: int,
    ) -> list[WearingItem]:
        try:
            response = await self._http.get(
                "avatar",
                f"/v1/users/{user_id}/currently-wearing",
            )

            asset_ids = response.get(
                "assetIds", []
            )
            return [
                WearingItem(asset_id=asset_id)
                for asset_id in asset_ids
            ]
        except Exception as e:
            log.warning(
                "can't get avatar items for user %d: %s",
                user_id,
                e,
            )
            return []

    @rate_limit(calls_per_minute=120)
    @retry_on_failure(max_retries=3)
    async def get_user_limited_items(
        self,
        user_id: int,
        limit: int = 10,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        allowed_limits = [10, 25, 50, 100]
        if limit not in allowed_limits:
            limit = min(
                allowed_limits,
                key=lambda x: abs(x - limit),
            )

        params = {
            "assetType": "All",
            "limit": limit,
            "sortOrder": "Desc",
        }

        if cursor:
            params["cursor"] = cursor

        try:
            response = await self._http.get(
                "inventory",
                f"/v1/users/{user_id}/assets/collectibles",
                params=params,
            )

            limited_items = []
            for item_data in response.get(
                "data", []
            ):
                try:
                    limited_items.append(
                        self._parse_limited_item(
                            item_data
                        )
                    )
                except Exception:
                    log.exception(
                        "limited item data is messed up: %s",
                        item_data,
                    )
                    continue

            return {
                "limited_items": limited_items,
                "previous_cursor": response.get(
                    "previousPageCursor"
                ),
                "next_cursor": response.get(
                    "nextPageCursor"
                ),
            }
        except Exception as e:
            log.warning(
                "can't get collectibles for user %d: %s",
                user_id,
                e,
            )
            return {
                "limited_items": [],
                "previous_cursor": None,
                "next_cursor": None,
            }

    @staticmethod
    def _parse_user_profile(
        data: dict[str, Any],
    ) -> UserProfile:
        created = data.get("created")
        created_date = (
            datetime.fromisoformat(created)
            if created
            else None
        )

        return UserProfile(
            id=data["id"],
            username=data["name"],
            display_name=data["displayName"],
            description=data.get(
                "description", ""
            ),
            created_date=created_date,
            follower_count=0,
            following_count=0,
            friend_count=0,
            is_verified=data.get(
                "hasVerifiedBadge", False
            ),
        )

    @staticmethod
    def _parse_user_profile_simple(
        data: dict[str, Any],
    ) -> UserProfile:
        return UserProfile(
            id=data["id"],
            username=data["name"],
            display_name=data["displayName"],
            description="",
            created_date=None,
            follower_count=0,
            following_count=0,
            friend_count=0,
            is_verified=data.get(
                "hasVerifiedBadge", False
            ),
        )

    @staticmethod
    def _extract_thumbnail_url(
        response: dict[str, Any],
    ) -> str:
        data = response.get("data")
        if not data:
            return ""
        return data[0].get("imageUrl", "")

    @staticmethod
    def _parse_user_badge(
        data: dict[str, Any],
    ) -> UserBadge:
        created = data.get("created")
        created_date = (
            datetime.fromisoformat(
                created.replace("Z", "+00:00")
            )
            if created
            else None
        )

        statistics = data.get("statistics", {})

        return UserBadge(
            id=data["id"],
            name=data["name"],
            description=data.get(
                "description", ""
            ),
            enabled=data.get("enabled", True),
            icon_image_id=data.get(
                "iconImageId", 0
            ),
            created=created_date,
            awarded_count=statistics.get(
                "awardedCount", 0
            ),
            win_rate_percentage=statistics.get(
                "winRatePercentage", 0.0
            ),
        )

    @staticmethod
    def _parse_user_presence(
        data: dict[str, Any],
    ) -> UserPresence:
        return UserPresence(
            user_id=data["userId"],
            presence_type=data.get(
                "userPresenceType", 0
            ),
            last_location=data.get(
                "lastLocation", ""
            ),
            place_id=data.get("placeId"),
            root_place_id=data.get("rootPlaceId"),
            game_id=data.get("gameId"),
            universe_id=data.get("universeId"),
        )

    @staticmethod
    def _parse_game_basic(
        data: dict[str, Any],
    ) -> Game:
        created = data.get("created")
        created_date = (
            datetime.fromisoformat(
                created.replace("Z", "+00:00")
            )
            if created
            else None
        )

        creator = data.get("creator", {})

        return Game(
            id=data.get("id", 0),
            root_place_id=data.get(
                "rootPlaceId", 0
            ),
            name=data.get("name", ""),
            description=data.get(
                "description", ""
            ),
            creator_id=creator.get("id", 0),
            creator_name=creator.get("name", ""),
            creator_type=creator.get(
                "type", "User"
            ),
            playing=data.get("playing", 0),
            visits=data.get("visits", 0),
            max_players=data.get("maxPlayers", 0),
            created=created_date,
            genre=data.get("genre", ""),
        )

    @staticmethod
    def _parse_game_detailed(
        data: dict[str, Any],
    ) -> Game:
        created = data.get("created")
        created_date = (
            datetime.fromisoformat(
                created.replace("Z", "+00:00")
            )
            if created
            else None
        )

        creator = data.get("creator", {})

        return Game(
            id=data["id"],
            root_place_id=data["rootPlaceId"],
            name=data["name"],
            description=data.get(
                "description", ""
            ),
            creator_id=creator.get("id", 0),
            creator_name=creator.get("name", ""),
            creator_type=creator.get(
                "type", "User"
            ),
            playing=data.get("playing", 0),
            visits=data.get("visits", 0),
            max_players=data.get("maxPlayers", 0),
            created=created_date,
            genre=data.get("genre", ""),
        )

    @staticmethod
    def _parse_limited_item(
        data: dict[str, Any],
    ) -> LimitedItem:
        return LimitedItem(
            user_asset_id=data.get(
                "userAssetId", 0
            ),
            serial_number=data.get(
                "serialNumber", 0
            ),
            asset_id=data.get("assetId", 0),
            name=data.get("name", ""),
            recent_average_price=data.get(
                "recentAveragePrice", 0
            ),
            original_price=data.get(
                "originalPrice", 0
            ),
            asset_stock=data.get("assetStock", 0),
            is_on_hold=data.get(
                "isOnHold", False
            ),
        )
