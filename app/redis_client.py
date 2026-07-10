"""Factory for Redis clients hardened against dropped remote connections.

Source and history Redis live on a remote host, so idle TCP connections can be
reaped by the server or an intervening firewall/NAT. When redis-py later hands
out one of those dead sockets it surfaces as a ConnectionError such as WinError
10054 ("An existing connection was forcibly closed by the remote host").

These options keep connections warm (TCP keepalive), detect stale command
connections before reuse (health check), and let redis-py transparently retry a
single dropped socket instead of raising.
"""
from typing import Any

from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.retry import Retry


def create_redis_client(url: str, decode_responses: bool = True, **overrides: Any) -> Redis:
    options: dict[str, Any] = {
        "decode_responses": decode_responses,
        "socket_keepalive": True,
        "socket_connect_timeout": 5,
        "health_check_interval": 30,
        "retry": Retry(ExponentialBackoff(), 3),
        "retry_on_error": [RedisConnectionError, RedisTimeoutError],
    }
    options.update(overrides)
    return Redis.from_url(url, **options)
