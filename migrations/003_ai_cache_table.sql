-- Migration 003: Add AI Response Cache Table
-- Purpose: Optimize API quota by caching AI responses for similar queries
-- Impact: Reduces Gemini API calls by using database-backed similarity matching

CREATE TABLE IF NOT EXISTS ai_response_cache (
    id SERIAL PRIMARY KEY,
    user_query_hash VARCHAR(64) UNIQUE NOT NULL,
    user_query TEXT NOT NULL,
    ai_answer TEXT NOT NULL,
    use_count INT DEFAULT 1,
    similarity_threshold INT DEFAULT 90,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_query_hash (user_query_hash),
    INDEX idx_last_used (last_used_at),
    INDEX idx_created (created_at)
);

-- Add comment
COMMENT ON TABLE ai_response_cache IS 'Cache for AI responses to reduce quota usage. Stores query hash, original query, and AI response for similarity matching';
COMMENT ON COLUMN ai_response_cache.user_query_hash IS 'SHA256 hash of the user query (lowercase, trimmed)';
COMMENT ON COLUMN ai_response_cache.user_query IS 'Original user query for debugging and similarity comparison';
COMMENT ON COLUMN ai_response_cache.ai_answer IS 'The AI-generated response that was cached';
COMMENT ON COLUMN ai_response_cache.use_count IS 'Tracks how many times this cached response was reused';
COMMENT ON COLUMN ai_response_cache.similarity_threshold IS 'Minimum similarity percentage (0-100) required to return cached answer';
COMMENT ON COLUMN ai_response_cache.last_used_at IS 'Timestamp of last reuse, for maintenance and analytics';

-- Optional: Create a view for cache analytics
CREATE OR REPLACE VIEW cache_analytics AS
SELECT 
    COUNT(*) as total_cached_queries,
    SUM(use_count) as total_uses,
    COUNT(*) as total_entries,
    ROUND(100.0 * (SUM(use_count) - COUNT(*)) / SUM(use_count), 2) as efficiency_percentage,
    MAX(last_used_at) as last_used,
    MIN(created_at) as created_from
FROM ai_response_cache;

-- Maintenance: Drop old cache entries
-- OPTIONAL: Uncomment to delete cache entries older than 30 days
-- DELETE FROM ai_response_cache WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
