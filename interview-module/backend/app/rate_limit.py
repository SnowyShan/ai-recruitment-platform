import time
from collections import defaultdict
from threading import Lock
from fastapi import Request, HTTPException


class RateLimiter:
    def __init__(self, requests: int, period: float):
        self.requests = requests
        self.period = period
        self.clients: dict = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, client_id: str) -> bool:
        with self.lock:
            now = time.time()
            cutoff = now - self.period
            self.clients[client_id] = [t for t in self.clients[client_id] if t > cutoff]
            if len(self.clients[client_id]) >= self.requests:
                return False
            self.clients[client_id].append(now)
            return True


def get_remote_address(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


rate_limiter = RateLimiter(requests=300, period=60.0)


def rate_limit_dependency(request: Request):
    client_id = get_remote_address(request)
    if False:  # rate limiting disabled
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded: 20 requests per minute"
        )
