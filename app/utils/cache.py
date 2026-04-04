"""
Cache Manager - Reduce Gemini API calls with Database-backed caching
Uses database for persistent cache with TTL and similarity matching
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from db import models

logger = logging.getLogger(__name__)


def hash_query(query: str) -> str:
    """
    Generate SHA256 hash of a query for cache lookup
    
    Args:
        query: User query string
        
    Returns:
        SHA256 hash of the query
    """
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate string similarity between two texts using SequenceMatcher
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score between 0-100
    """
    ratio = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    return round(ratio * 100, 2)


def find_cached_response(
    user_query: str,
    db: Session,
    min_similarity: int = 90
) -> Optional[dict]:
    """
    Search for a cached response - first exact match, then similarity match
    
    Strategy:
    1. Try exact hash match first (very fast O(1))
    2. If not found, do similarity check on recent queries (O(n) on recent data)
    
    Args:
        user_query: User's query
        db: Database session
        min_similarity: Minimum similarity percentage (default 90%)
        
    Returns:
        Dictionary with 'answer' and 'similarity_score' if found, None otherwise
    """
    try:
        query_hash = hash_query(user_query)
        
        # 1. Try exact match first
        cached = db.query(models.AIResponseCache).filter(
            models.AIResponseCache.user_query_hash == query_hash
        ).first()
        
        if cached:
            # Increment use count
            cached.use_count += 1
            cached.last_used_at = datetime.utcnow()
            db.commit()
            logger.info(f"Cache HIT (exact match) - Query: {user_query[:40]}...")
            return {
                "answer": cached.ai_answer,
                "similarity_score": 100,
                "cache_id": cached.id
            }
        
        # 2. Similarity check on recent cached queries
        # Only check recent queries to avoid performance issues
        recent_caches = db.query(models.AIResponseCache).order_by(
            models.AIResponseCache.last_used_at.desc()
        ).limit(50).all()
        
        for cache in recent_caches:
            similarity = calculate_similarity(user_query, cache.user_query)
            
            if similarity >= min_similarity:
                cache.use_count += 1
                cache.last_used_at = datetime.utcnow()
                db.commit()
                logger.info(
                    f"Cache HIT (similarity: {similarity}%) - Similar to: {cache.user_query[:40]}..."
                )
                return {
                    "answer": cache.ai_answer,
                    "similarity_score": similarity,
                    "cache_id": cache.id
                }
        
        logger.info(f"Cache MISS - No similar queries found for: {user_query[:40]}...")
        return None
        
    except Exception as e:
        logger.error(f"Error finding cached response: {e}")
        return None


def save_to_cache(
    user_query: str,
    ai_answer: str,
    db: Session
) -> bool:
    """
    Save AI response to cache
    
    Args:
        user_query: Original user query
        ai_answer: AI's response
        db: Database session
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        query_hash = hash_query(user_query)
        
        # Check if already exists
        existing = db.query(models.AIResponseCache).filter(
            models.AIResponseCache.user_query_hash == query_hash
        ).first()
        
        if existing:
            # Update if exists
            existing.ai_answer = ai_answer
            existing.use_count += 1
            logger.info(f"Updated cache - Query: {user_query[:40]}...")
        else:
            # Create new cache entry
            cache_entry = models.AIResponseCache(
                user_query_hash=query_hash,
                user_query=user_query,
                ai_answer=ai_answer,
                use_count=1
            )
            db.add(cache_entry)
            logger.info(f"Saved new cache - Query: {user_query[:40]}...")
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error saving to cache: {e}")
        db.rollback()
        return False


def clear_old_cache(days: int = 30, db: Session = None) -> int:
    """
    Clear cache entries older than specified days
    Good for maintenance to prevent database bloat
    
    Args:
        days: Delete entries older than this many days
        db: Database session
        
    Returns:
        Number of entries deleted
    """
    if not db:
        return 0
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        deleted_count = db.query(models.AIResponseCache).filter(
            models.AIResponseCache.created_at < cutoff_date
        ).delete()
        
        db.commit()
        logger.info(f"Cache maintenance: Deleted {deleted_count} old entries (older than {days} days)")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error clearing old cache: {e}")
        db.rollback()
        return 0


def get_cache_stats(db: Session) -> dict:
    """
    Get cache performance statistics
    Useful for monitoring cache effectiveness
    
    Returns:
        Dictionary with cache statistics
    """
    try:
        total_entries = db.query(models.AIResponseCache).count()
        total_reuse = db.query(models.AIResponseCache).filter(
            models.AIResponseCache.use_count > 1
        ).count()
        
        sum_use_count = db.query(models.AIResponseCache).with_entities(
            db.func.sum(models.AIResponseCache.use_count)
        ).scalar() or 0
        
        # Calculate API calls saved by using cache
        api_calls_saved = sum_use_count - total_entries if sum_use_count > 0 else 0
        
        return {
            "total_cached_queries": total_entries,
            "reused_queries": total_reuse,
            "api_calls_saved": api_calls_saved,
            "efficiency": f"{(api_calls_saved / sum_use_count * 100):.1f}%" if sum_use_count > 0 else "0%"
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {}


# Legacy in-memory cache support (for backward compatibility)
class ResponseCache:
    """
    Simple in-memory cache with TTL support
    For database-backed caching, use functions above instead
    """
    
    def __init__(self, ttl_hours: int = 24):
        self.cache = {}  # {hash: {'response': str, 'expires': datetime}}
        self.ttl = timedelta(hours=ttl_hours)
    
    @staticmethod
    def _hash_query(user_message: str, context: str = None) -> str:
        """Create hash of message + context for cache key"""
        query = f"{user_message.lower().strip()}:{context or ''}"
        return hashlib.md5(query.encode()).hexdigest()
    
    def get(self, user_message: str, context: str = None) -> Optional[str]:
        """Get cached response if exists and not expired"""
        cache_key = self._hash_query(user_message, context)
        
        if cache_key not in self.cache:
            return None
        
        cached = self.cache[cache_key]
        if datetime.now() > cached.get('expires'):
            del self.cache[cache_key]
            return None
        
        return cached['response']
    
    def set(self, user_message: str, response: str, context: str = None) -> None:
        """Store response in cache with TTL"""
        cache_key = self._hash_query(user_message, context)
        self.cache[cache_key] = {
            'response': response,
            'expires': datetime.now() + self.ttl
        }
    
    def clear(self) -> None:
        """Clear entire cache"""
        self.cache.clear()

        
        if cache_key not in self.cache:
            return None
        
        cached = self.cache[cache_key]
        
        # Check if expired
        if datetime.now() > cached['expires']:
            del self.cache[cache_key]
            logger.info(f"🗑️ Cache expired for key: {cache_key}")
            return None
        
        logger.info(f"✅ Cache HIT for message: {user_message[:50]}...")
        return cached['response']
    
    def set(self, user_message: str, response: str, context: str = None) -> None:
        """
        Store response in cache
        
        Args:
            user_message: User's input message
            response: AI response to cache
            context: System context
        """
        cache_key = self._hash_query(user_message, context)
        self.cache[cache_key] = {
            'response': response,
            'expires': datetime.now() + self.ttl,
            'created': datetime.now()
        }
        logger.info(f"💾 Cache SET for message: {user_message[:50]}...")
    
    def clear_expired(self) -> int:
        """Remove expired cache entries. Call periodically."""
        expired_keys = [
            k for k, v in self.cache.items() 
            if datetime.now() > v['expires']
        ]
        for k in expired_keys:
            del self.cache[k]
        if expired_keys:
            logger.info(f"🗑️ Cleared {len(expired_keys)} expired cache entries")
        return len(expired_keys)
    
    def stats(self) -> dict:
        """Get cache statistics"""
        self.clear_expired()  # Clean before reporting
        return {
            'total_entries': len(self.cache),
            'cache_size_mb': self._estimate_size(),
            'ttl_hours': self.ttl.total_seconds() / 3600
        }
    
    def _estimate_size(self) -> float:
        """Estimate cache size in MB"""
        size = 0
        for entry in self.cache.values():
            size += len(str(entry).encode('utf-8'))
        return round(size / 1024 / 1024, 2)
    
    def __repr__(self) -> str:
        stats = self.stats()
        return f"Cache({stats['total_entries']} entries, {stats['cache_size_mb']}MB)"


# Global cache instance
_response_cache = ResponseCache(ttl_hours=24)

def get_cache() -> ResponseCache:
    """Get global cache instance"""
    return _response_cache

def cache_get(user_message: str, context: str = None) -> Optional[str]:
    """Utility function to get from cache"""
    return _response_cache.get(user_message, context)

def cache_set(user_message: str, response: str, context: str = None) -> None:
    """Utility function to set cache"""
    _response_cache.set(user_message, response, context)

def cache_stats() -> dict:
    """Get cache statistics"""
    return _response_cache.stats()
