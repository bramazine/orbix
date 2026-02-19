from __future__ import annotations

import time
from asyncio import sleep
from collections import OrderedDict, deque
from functools import lru_cache, wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import (
        Awaitable,
        Callable,
    )

from ..exceptions import RateLimitError

T = TypeVar("T")


def rate_limit(
    calls_per_minute: int = 60,
) -> Callable[
    [Callable[..., Awaitable[T]]],
    Callable[..., Awaitable[T]],
]:
    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        call_times: deque[float] = deque()

        @wraps(func)
        async def wrapper(
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> T:
            now = time.time()

            while (
                call_times
                and now - call_times[0] >= 60
            ):
                call_times.popleft()

            if (
                len(call_times)
                >= calls_per_minute
            ):
                sleep_time = 60 - (
                    now - call_times[0]
                )
                raise RateLimitError(
                    int(sleep_time)
                )

            call_times.append(now)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def retry_on_failure(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
) -> Callable[
    [Callable[..., Awaitable[T]]],
    Callable[..., Awaitable[T]],
]:
    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> T:
            last_exception: Exception | None = (
                None
            )

            for attempt in range(max_retries + 1):
                try:
                    return await func(
                        *args, **kwargs
                    )
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    await sleep(
                        backoff_factor
                        * (2**attempt)
                    )

            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator


_API_ENDPOINTS: dict[str, str] = {
    "users": "https://users.roblox.com",
    "thumbnails": "https://thumbnails.roblox.com",
    "games": "https://games.roblox.com",
    "badges": "https://badges.roblox.com",
    "friends": "https://friends.roblox.com",
    "presence": "https://presence.roblox.com",
}


@lru_cache(maxsize=128)
def get_api_endpoint(
    endpoint_type: str,
) -> str:
    return _API_ENDPOINTS.get(
        endpoint_type,
        "https://api.roblox.com",
    )


class APICache:
    def __init__(
        self,
        ttl: int = 300,
        max_size: int = 1000,
    ) -> None:
        self._cache: OrderedDict[
            str, tuple[float, Any]
        ] = OrderedDict()
        self._ttl = ttl
        self._max_size = max_size

    def get(self, key: str) -> Any | None:  # noqa: ANN401
        if key not in self._cache:
            return None

        timestamp, value = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None

        self._cache.move_to_end(key)
        return value

    def set(
        self,
        key: str,
        value: Any,  # noqa: ANN401
    ) -> None:
        if key in self._cache:
            del self._cache[key]

        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = (
            time.time(),
            value,
        )

    def clear(self) -> None:
        self._cache.clear()

    def get_stats(self) -> dict[str, int]:
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl": self._ttl,
        }
