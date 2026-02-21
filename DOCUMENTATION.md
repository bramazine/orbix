<div align="center">

# orbix

A considered approach to the Roblox API.

</div>

---



**table of contents**

- [Installation](#installation)
- [Usage](#usage)
- [Client](#client)
- [Methods](#methods)
- [Models](#models)
- [Errors](#errors)
- [Rate Limiting](#rate-limiting)
- [Caching](#caching)
- [Performance Monitoring](#performance-monitoring)


---

## Installation

```bash

pip install git+ssh://git@github.com/bramazine/orbix.git
```

This equires Python 3.12 or later. You also must have `aiohttp>=3.9.0`.

---

## Usage

```py

from asyncio import run
from orbix import OrbixClient

async def main():
    async with OrbixClient() as client:
        user = await client.get_user(555)
        print(user.display_name)

run(main())
```

The context manager ensures all connections are closed when the block exits. If you manage the lifecycle manually, call `await client.close()` when you're done.

---

## Client

```py

OrbixClient(timeout: int = 30, cache_ttl: int = 300)
```

| Parameter | Default | Purpose |
|:--|:--|:--|
| `timeout` | `30` | Request timeout (seconds) |
| `cache_ttl` | `300` | LRU cache expiry (seconds) |

Both values can be sourced from environment variables if preferred:

```py

import os

client = OrbixClient(
    timeout=int(os.getenv("ORBIX_TIMEOUT", 30)),
    cache_ttl=int(os.getenv("ORBIX_CACHE_TTL", 300)),
)
```

---

## Methods

### Users

| Method | Returns | Description |
|:--|:--|:--|
| `get_user(user_id)` | `UserProfile` | full profile with social counts fetched concurrently |
| `get_user_by_username(username)` | `UserProfile` | resolves username, then fetches full profile |
| `get_users_batch(user_ids)` | `list[UserProfile]` | batch fetch up to 100 users in one request |

Batch responses may return simplified profiles without `created_date` depending on the API's response. Orbix handles this transparently.

### Avatars

| Method | Returns | Description |
|:--|:--|:--|
| `get_user_avatar(user_id, headshot_size, bust_size, full_body_size)` | `UserAvatar` | fetches headshot, bust, and full body thumbnails concurrently |

Default sizes are `48x48` for headshot and bust, `150x150` for full body. Other sizes are `30x30`, `48x48`, `60x60`, `75x75`, `100x100`, `150x150`, `180x180`, `352x352`, `420x420`.

### Social

| Method | Returns | Description |
|:--|:--|:--|
| `get_user_followers(user_id, limit=10)` | `list[UserProfile]` | follower profiles (max 100) |
| `get_user_following(user_id, limit=10)` | `list[UserProfile]` | following profiles (max 100) |
| `get_user_friends(user_id, limit=10)` | `list[UserProfile]` | friend profiles (max 100) |
| `get_user_follower_count(user_id)` | `int` | follower count |
| `get_user_following_count(user_id)` | `int` | following count |
| `get_user_friend_count(user_id)` | `int` | friend count |
| `get_user_badges(user_id, limit=10, cursor=None)` | `dict` | user badges with pagination |
| `get_user_presence(user_ids)` | `list[UserPresence]` | online status for multiple users |
| `get_user_favourite_games(user_id, limit=10, cursor=None)` | `dict` | favourite games with pagination |
| `get_game_details(universe_ids)` | `list[Game]` | game info for multiple universes |
| `get_user_currently_wearing(user_id)` | `list[WearingItem]` | avatar items currently equipped |
| `get_user_limited_items(user_id, limit=10, cursor=None)` | `dict` | collectibles/limiteds with pagination |

### Utility

| Method | Returns | Description |
|:--|:--|:--|
| `warm_cache(user_ids)` | `None` | pre-fetches users in batches of 50 for cache priming |
| `close()` | `None` | closes the underlying HTTP session |

---

## Models

```py

from orbix import (
    OrbixClient,
    UserProfile, 
    UserAvatar, 
    UserBadge, 
    UserPresence,
    Game, FavouriteGame, 
    WearingItem, 
    LimitedItem,
    UserNotFoundError
)
```

### UserProfile

Frozen dataclass. All are immutable instances;

| Field | Type | Notes |
|:--|:--|:--|
| `id` | `int` | |
| `username` | `str` | |
| `display_name` | `str` | |
| `description` | `str` | |
| `created_date` | `datetime \| None` | |
| `follower_count` | `int` | |
| `following_count` | `int` | |
| `friend_count` | `int` | |
| `is_verified` | `bool` | |

### UserBadge

| Field | Type | Notes |
|:--|:--|:--|
| `id` | `int` | |
| `name` | `str` | |
| `description` | `str` | |
| `enabled` | `bool` | |
| `icon_image_id` | `int` | |
| `created` | `datetime \| None` | |
| `awarded_count` | `int` | |
| `win_rate_percentage` | `float` | |

### UserPresence

| Field | Type | Notes |
|:--|:--|:--|
| `user_id` | `int` | |
| `presence_type` | `int` | 0=offline, 1=online, 2=ingame, 3=studio |
| `last_location` | `str` | |
| `place_id` | `int \| None` | |
| `root_place_id` | `int \| None` | |
| `game_id` | `int \| None` | |
| `universe_id` | `int \| None` | |

### Game

| Field | Type | Notes |
|:--|:--|:--|
| `id` | `int` | universe id |
| `root_place_id` | `int` | |
| `name` | `str` | |
| `description` | `str` | |
| `creator_id` | `int` | |
| `creator_name` | `str` | |
| `creator_type` | `str` | User or Group |
| `playing` | `int` | current players |
| `visits` | `int` | total visits |
| `max_players` | `int` | |
| `created` | `datetime \| None` | |
| `genre` | `str` | |

### FavouriteGame

| Field | Type | Notes |
|:--|:--|:--|
| `game` | `Game` | |

### WearingItem

| Field | Type | Notes |
|:--|:--|:--|
| `asset_id` | `int` | |

### LimitedItem

| Field | Type | Notes |
|:--|:--|:--|
| `user_asset_id` | `int` | unique instance id |
| `serial_number` | `int` | 0 if not numbered |
| `asset_id` | `int` | |
| `name` | `str` | |
| `recent_average_price` | `int` | robux |
| `original_price` | `int` | robux |
| `asset_stock` | `int` | total copies |
| `is_on_hold` | `bool` | trading status |
| `profile_url` | `str` | computed property |

### UserAvatar

Frozen dataclass.

| Field | Type |
|:--|:--|
| `user_id` | `int` |
| `headshot_url` | `str` |
| `bust_url` | `str` |
| `full_body_url` | `str` |

---

## Errors

```
RobloxAPIError
├── UserNotFoundError
├── RateLimitError
└── NetworkError
```

| Exception | Key Attributes | Raised When |
|:--|:--|:--|
| `RobloxAPIError` | `message`, `status_code` | any non 200 API response |
| `UserNotFoundError` | `user_identifier` | user does not exist |
| `RateLimitError` | `retry_after` | rate limit exceeded |
| `NetworkError` | `original_error` | connection failure or timeout |

All exceptions are importable from `orbix` directly.

```py
from orbix import UserNotFoundError, RateLimitError, NetworkError
```

---

## Rate Limiting

Every API method is decorated with automatic rate limiting. Limits are per-method and measured over a rolling 60 second window. If the threshold is exceeded, a `RateLimitError` is raised && the caller decides whether to wait or fail.

| Method Group | Limit |
|:--|:--|
| user / batch / social lists | 120 calls/min |
| avatars / badges / presence / games / inventory | 120 calls/min |
| avatar thumbnails | 180 calls/min |
| social counts | 60 calls/min |

Failed requests are retried up to 3 times with exponential backoff.

---

## Caching

GET requests are cached in an LRU cache keyed by method, URL, and sorted parameters. The cache is bounded (1000 entries by default) and entries expire after `cache_ttl` seconds. POST requests are never cached.

`warm_cache(user_ids)` pre-fetches users in batches of 50, populating the cache for subsequent lookups.

---

## Performance Monitoring

```py

from orbix.core import PerformanceMonitor

monitor = PerformanceMonitor()
```

| Method | Returns |
|:--|:--|
| `get_stats(last_n=100)` | `dict` — `total_requests`, `avg_duration`, `success_rate`, `cache_hit_rate`, `fastest_request`, `slowest_request` |
| `get_endpoint_stats()` | `dict[str, dict]` — per-endpoint breakdown |
| `clear_metrics()` | `None` |

---

<sub>I am NOT affiliated with Roblox Corporation.</sub>