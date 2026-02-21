from __future__ import annotations

import builtins
import logging
from asyncio import sleep
from json import JSONDecodeError, dumps
from typing import Any, Self

from aiohttp import (
    ClientError,
    ClientResponse,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
    TCPConnector,
)

from ..exceptions import (
    NetworkError,
    RateLimitError,
    RobloxAPIError,
    UserNotFoundError,
)
from .utils import APICache, get_api_endpoint

log = logging.getLogger(__name__)


class HTTPClient:
    def __init__(
        self,
        timeout: int = 30,
        cache_ttl: int = 300,
    ) -> None:
        self._session: ClientSession | None = None
        self._timeout = ClientTimeout(
            total=timeout
        )
        self._cache = APICache(ttl=cache_ttl)
        self._headers = {
            "User-Agent": "orbix/1.0.0 (+https://github.com/bramazine/orbix)",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _create_connector(self) -> TCPConnector:
        return TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
        )

    @property
    def session(self) -> ClientSession:
        if (
            self._session is None
            or self._session.closed
        ):
            self._session = ClientSession(
                timeout=self._timeout,
                headers=self._headers,
                connector=self._create_connector(),
            )
        return self._session

    async def close(self) -> None:
        if (
            self._session
            and not self._session.closed
        ):
            await self._session.close()
            await sleep(0.1)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,  # ;;
        exc_val: BaseException | None,  # ;;
        exc_tb: object | None,  # ;;
    ) -> None:
        await self.close()

    async def request(
        self,
        method: str,
        endpoint_type: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        base_url = get_api_endpoint(endpoint_type)
        url = f"{base_url}{path}"

        cache_key = (
            f"{method}:{url}:"
            f"{dumps(params, sort_keys=True) if params else ''}"
        )
        if method == "GET" and use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            async with self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
            ) as response:
                await (
                    self._handle_response_errors(
                        response
                    )
                )

                response_data = (
                    await response.json()
                )

                if method == "GET" and use_cache:
                    self._cache.set(
                        cache_key,
                        response_data,
                    )

                return response_data

        except ClientError as e:
            raise NetworkError(e) from e
        except builtins.TimeoutError as e:
            raise NetworkError(e) from e

    async def _handle_response_errors(
        self,
        response: ClientResponse,
    ) -> None:
        if response.status == 200:
            return

        if response.status == 404:
            if "/users/" in str(response.url):
                raise UserNotFoundError(
                    str(response.url)
                )
            raise RobloxAPIError(
                "resource not found",
                response.status,
            )

        if response.status == 429:
            retry_after = response.headers.get(
                "Retry-After"
            )
            raise RateLimitError(
                int(retry_after)
                if retry_after
                else None
            )

        try:
            error_data = await response.json()
            error_message = error_data.get(
                "message",
                f"HTTP {response.status}",
            )
        except (
            JSONDecodeError,
            ContentTypeError,
        ):
            error_message = (
                f"HTTP {response.status}"
            )

        raise RobloxAPIError(
            error_message, response.status
        )

    async def get(
        self,
        endpoint_type: str,
        path: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        return await self.request(
            "GET",
            endpoint_type,
            path,
            params=params,
            use_cache=use_cache,
        )

    async def post(
        self,
        endpoint_type: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.request(
            "POST",
            endpoint_type,
            path,
            params=params,
            data=data,
            use_cache=False,
        )
