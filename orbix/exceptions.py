from __future__ import annotations


class RobloxAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UserNotFoundError(RobloxAPIError):
    def __init__(
        self, 
        user_identifier: str,
    ) -> None:
        message = f"requested user @{user_identifier} not found"
        super().__init__(message)
        self.user_identifier = user_identifier


class RateLimitError(RobloxAPIError):
    def __init__(
        self,
        retry_after: int | None = None,
    ) -> None:
        message = "rate limited"
        if retry_after:
            message += (
                f", retry after {retry_after}s"
            )
        super().__init__(message)
        self.retry_after = retry_after


class NetworkError(RobloxAPIError):
    def __init__(
        self,
        original_error: Exception,
    ) -> None:
        super().__init__(str(original_error))
        self.original_error = original_error
