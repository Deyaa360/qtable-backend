from functools import wraps
from typing import Optional, Dict, Any
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Simple in-memory cache for now (Redis implementation can be added later)
class SimpleCache:
    def __init__(self, default_timeout: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_timeout = default_timeout
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self._cache:
            item = self._cache[key]
            if datetime.now() < item['expires']:
                return item['value']
            else:
                # Expired, remove it
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> None:
        """Set value in cache"""
        if timeout is None:
            timeout = self.default_timeout
        
        self._cache[key] = {
            'value': value,
            'expires': datetime.now() + timedelta(seconds=timeout),
            'created': datetime.now()
        }
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache"""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired items and return count removed"""
        now = datetime.now()
        expired_keys = [k for k, v in self._cache.items() if now >= v['expires']]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

# Global cache instance
cache = SimpleCache()

def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_parts = []
    for arg in args:
        if hasattr(arg, 'id'):
            key_parts.append(f"{type(arg).__name__}:{arg.id}")
        else:
            key_parts.append(str(arg))
    
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{v}")
    
    return ":".join(key_parts)

def cached(timeout: int = 300, key_prefix: str = ""):
    """Cache decorator for functions (sync and async)"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit for key: {key}")
                return result
            
            # Execute function and cache result
            logger.debug(f"Cache miss for key: {key}")
            result = await func(*args, **kwargs)
            cache.set(key, result, timeout)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit for key: {key}")
                return result
            
            # Execute function and cache result
            logger.debug(f"Cache miss for key: {key}")
            result = func(*args, **kwargs)
            cache.set(key, result, timeout)
            return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
        
    return decorator

def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate cache keys matching pattern"""
    removed = 0
    keys_to_remove = [k for k in cache._cache.keys() if pattern in k]
    for key in keys_to_remove:
        cache.delete(key)
        removed += 1
    logger.info(f"Invalidated {removed} cache entries matching pattern: {pattern}")
    return removed

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    now = datetime.now()
    total_items = len(cache._cache)
    expired_items = sum(1 for v in cache._cache.values() if now >= v['expires'])
    
    return {
        'total_items': total_items,
        'expired_items': expired_items,
        'active_items': total_items - expired_items,
        'memory_usage_estimate': sum(len(str(v)) for v in cache._cache.values())
    }
