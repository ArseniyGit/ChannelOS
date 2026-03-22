from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

_WINDOWS: dict[str, deque[float]] = {}
_LOCK = Lock()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = forwarded_for.split(",", 1)[0].strip()
        if first_ip:
            return first_ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
    detail: str = "Too many requests. Please try again later.",
) -> None:
    if limit <= 0:
        return

    now = monotonic()
    cutoff = now - window_seconds

    with _LOCK:
        bucket = _WINDOWS.setdefault(key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
            )

        bucket.append(now)
