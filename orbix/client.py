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
from .models import UserAvatar, UserProfile

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
                "unable to fetch counts for user %d",
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
