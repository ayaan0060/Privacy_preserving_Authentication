# phase5_backend/backend/security/rate_limit.py
"""
Redis-backed Rate Limiting.
Sliding window with burst allowance.
"""
import time
from typing import Optional, Tuple, Dict
import redis.asyncio as redis
from fastapi import Request, HTTPException, status
from functools import wraps

from ..config import get_settings


class RateLimiter:
    def __init__(self):
        self.settings = get_settings()
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        try:
            self.redis_client = redis.from_url(
                self.settings.redis.url,
                max_connections=self.settings.redis.max_connections,
                decode_responses=True,
            )
        except Exception:
            self.redis_client = None
    
    async def close(self):
        if self.redis_client:
            await self.redis_client.close()
    
    async def check_rate_limit(
        self, 
        key: str, 
        limit: int, 
        window_seconds: int = 60,
        burst_multiplier: int = 2
    ) -> Tuple[bool, Dict]:
        """
        Check rate limit using sliding window.
        Returns (allowed, metadata).
        """
        if not self.redis_client:
            return True, {}
        
        try:
            now = time.time()
            window_start = now - window_seconds
            redis_key = f"ratelimit:{key}"
            
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zadd(redis_key, {str(now): now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window_seconds + 1)
            results = await pipe.execute()
            
            current_count = results[2]
            effective_limit = limit * burst_multiplier
            
            allowed = current_count <= effective_limit
            
            metadata = {
                "limit": effective_limit,
                "remaining": max(0, effective_limit - current_count),
                "reset_at": now + window_seconds,
                "burst_used": current_count > limit,
            }
            
            return allowed, metadata
        except Exception:
            return True, {}


rate_limiter = RateLimiter()


async def rate_limit_dependency(
    request: Request,
    limit: int,
    window: int = 60,
):
    """FastAPI dependency for rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"{request.url.path}:{client_ip}"
    
    allowed, metadata = await rate_limiter.check_rate_limit(key, limit, window)
    request.state.rate_limit = metadata
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(metadata.get("limit", limit)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(metadata.get("reset_at", time.time() + window))),
            }
        )


def rate_limit(limit: int, window: int = 60):
    """Decorator for rate limiting endpoints."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get("request")
            
            if request:
                await rate_limit_dependency(request, limit, window)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
