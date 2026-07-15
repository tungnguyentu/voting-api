"""Factory for Redis clients hardened against dropped remote connections.

Source and history Redis live on a remote host, so idle TCP connections can be
reaped by the server or an intervening firewall/NAT. When redis-py later hands
out one of those dead sockets it surfaces as a ConnectionError such as WinError
10054 ("An existing connection was forcibly closed by the remote host").

These options keep connections warm (TCP keepalive), detect stale command
connections before reuse (health check), and let redis-py transparently retry a
single dropped socket instead of raising.

Docker note: containers may not route to LAN Redis (e.g. 10.x) the same way the
host process does. Prefer docker-compose host networking on Linux, or ensure the
Redis URL is reachable from inside the container (see README).
"""
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.retry import Retry


def redact_redis_url(url: str) -> str:
    """Hide password when logging Redis URLs."""
    try:
        parts = urlsplit(url)
        if parts.password is None:
            return url
        netloc = parts.hostname or ""
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        if parts.username:
            netloc = f"{parts.username}:***@{netloc}"
        else:
            netloc = f"***@{netloc}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return "<invalid-redis-url>"


def create_redis_client(url: str, decode_responses: bool = True, **overrides: Any) -> Redis:
    options: dict[str, Any] = {
        "decode_responses": decode_responses,
        "socket_keepalive": True,
        # Docker / VPN / LAN paths are often slower than localhost
        "socket_connect_timeout": 15,
        "socket_timeout": 30,
        "health_check_interval": 30,
        "retry": Retry(ExponentialBackoff(base=0.5, cap=5), 5),
        "retry_on_error": [RedisConnectionError, RedisTimeoutError],
    }
    options.update(overrides)
    return Redis.from_url(url, **options)


def ping_redis(client: Redis, label: str = "redis") -> None:
    """Fail fast with a clear message if Redis is unreachable (e.g. Docker network)."""
    ping = getattr(client, "ping", None)
    if not callable(ping):
        return
    try:
        ping()
    except Exception as exc:
        raise ConnectionError(
            f"Cannot reach {label}. "
            f"If running in Docker, the container may not route to Redis the same way "
            f"as host uvicorn/python. Check SOURCE_REDIS_URL / HISTORY_REDIS_URL and "
            f"Docker networking (see README). Underlying error: {exc}"
        ) from exc
