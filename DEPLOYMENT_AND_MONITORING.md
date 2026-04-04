# 🚀 FREE TIER OPTIMIZATION - DEPLOYMENT & MONITORING

## 📋 Deployment Checklist

### Pre-Deployment (Before Moving to Production)

- [x] **Code Review**
  - Strategy 1 (Input): Updated in `app/handlers/ai.py`
  - Strategy 2 (Rule-based): Verified in `app/handlers/router.py`
  - Strategy 3 (Cache): Implemented in `app/utils/cache.py`

- [x] **Database Schema**
  - Migration file created: `migrations/003_ai_cache_table.sql`
  - AI Response Cache table ready
  - Indexes for performance added

- [x] **Documentation**
  - `FREE_TIER_OPTIMIZATION_STRATEGY.md` - Full guide
  - `OPTIMIZATION_QUICK_REFERENCE.md` - Quick ref
  - `BEFORE_AFTER_COMPARISON.md` - Comparison

### Deployment Steps

#### Step 1: Backup Current Data (5 min)
```bash
# Create backup of current database
mysqldump -u root -p your_database > backup_before_optimization.sql

# Verify backup
ls -lh backup_before_optimization.sql
```

#### Step 2: Apply Database Migration (10 min)
```bash
# Option A: Using MySQL CLI
mysql -u root -p your_database < migrations/003_ai_cache_table.sql

# Option B: Using your migration runner
python -m alembic upgrade head
```

**Verify:**
```sql
-- Check if table created
SHOW TABLES LIKE 'ai_response_cache%';

-- Check structure
DESCRIBE ai_response_cache;

-- Check view created
SHOW CREATE VIEW cache_analytics;
```

#### Step 3: Verify Code Changes (5 min)
```bash
# Check AI handler limit change
grep "limit: int = 5" app/handlers/ai.py

# Check router priority
grep "PRIORITY 1\|PRIORITY 2\|PRIORITY 3" app/handlers/router.py

# Check cache functions exist
grep "def find_cached_response" app/utils/cache.py
grep "def save_to_cache" app/utils/cache.py
```

#### Step 4: Restart Application (5 min)
```bash
# Stop current instance
Ctrl+C
# Wait for graceful shutdown
sleep 3

# Start with optimized code
python -m app.main

# Or with uvicorn:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Verify logs:**
```
# Should show no errors
# Watch for "Cache" messages in logs
tail -f logs/app.log | grep -i "cache\|optimization"
```

#### Step 5: Test Optimization (15 min)

**Test 1: Input Optimization**
```bash
# Check if history is limited to 5
grep "limit\|history" logs/app.log | head -5
# Should show messages being limited to 5
```

**Test 2: Rule-Based (FAQ)**
```bash
# Send a FAQ message
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"message": {"text": "Giá xe 4 chỗ bao nhiêu?"}}'

# Check logs
tail -f logs/app.log | grep "FAQ match"
# Should show FAQ match instantly, no API call
```

**Test 3: Cache Hit**
```bash
# Send same message twice
curl -X POST http://localhost:8000/webhook \
  -d '{"message": {"text": "Hỏi du lịch Hội An"}}'

# Wait 1 second
sleep 1

# Send similar message
curl -X POST http://localhost:8000/webhook \
  -d '{"message": {"text": "Lên kế hoạch Hội An"}}'

# Check logs
tail -f logs/app.log | grep "Cache HIT"
# Should show cache hit on second message
```

---

## 📊 Monitoring & Analytics

### Real-Time Monitoring (First 24 hours)

#### Monitor Cache Growth
```python
#!/usr/bin/env python3
import time
from app.db.database import SessionLocal
from app.db.models import AIResponseCache

db = SessionLocal()

while True:
    count = db.query(AIResponseCache).count()
    print(f"[{time.strftime('%H:%M:%S')}] Cached queries: {count}")
    time.sleep(60)  # Check every minute
```

#### Monitor API Calls
```bash
# Watch logs for API calls
tail -f logs/app.log | grep -E "AI response generated|Cache HIT|FAQ match"

# Should show pattern like:
# FAQ match ... (0 tokens)
# Cache HIT ... (0 tokens)
# AI response ... (1,000 tokens)
```

### Daily Monitoring

#### Check Cache Statistics
```python
from app.utils.cache_monitor import CacheMonitor
from app.db.database import SessionLocal

db = SessionLocal()
monitor = CacheMonitor()

# Get performance report
report = monitor.get_performance_report(db)

print(f"""
📊 DAILY CACHE REPORT
⏰ {report['timestamp']}

Status: {report['status']}

💾 Cache Statistics:
  - Total cached queries: {report['cache_stats']['total_cached_queries']}
  - Reused queries: {report['cache_stats']['reused_queries']}
  - API calls saved: {report['cache_stats']['api_calls_saved']}
  - Efficiency: {report['cache_stats']['efficiency']}
  
📈 Metrics:
  - Avg response length: {report['metrics']['avg_response_length']}
  - Total storage: {report['metrics']['total_storage']}
  - High use entries: {report['metrics']['high_use_entries']}

💡 Recommendations:
""")

for rec in report['recommendations']:
    print(f"  • {rec}")
```

#### Check Top Cached Queries
```python
monitor = CacheMonitor()
top_queries = monitor.get_top_cached_queries(db, limit=10)

print("🔥 TOP 10 CACHED QUERIES")
for i, query_info in enumerate(top_queries, 1):
    print(f"{i}. Reused {query_info['reuse_count']} times")
    print(f"   Query: {query_info['query'][:80]}...")
    print(f"   Last used: {query_info['last_used']}")
```

### Weekly Monitoring

#### Performance Report
```python
# Run weekly (e.g., every Monday)
report = monitor.get_performance_report(db)

# Track these metrics:
metrics_to_track = {
    'timestamp': report['timestamp'],
    'cached_queries': report['cache_stats']['total_cached_queries'],
    'api_calls_saved': report['cache_stats']['api_calls_saved'],
    'efficiency': report['cache_stats']['efficiency'],
}

# Store in a log file or database for trending
```

#### Cache Cleanup
```python
# Delete old cache entries (older than 30 days)
result = monitor.perform_maintenance(db, days_to_keep=30)

print(f"""
🧹 CACHE MAINTENANCE COMPLETED
  - Deleted entries: {result['deleted_entries']}
  - Kept since: {result['before']['timestamp']}
  - Cache size now: {result['after']['total_cached_queries']} entries
""")
```

### Monthly Monitoring

#### Full Optimization Review
```python
print("=" * 60)
print("MONTHLY OPTIMIZATION REVIEW")
print("=" * 60)

# Get all metrics
stats = monitor.get_cache_stats(db)
top_queries = monitor.get_top_cached_queries(db, limit=20)

print(f"""
📊 Monthly Summary

Cache Performance:
  • Total cached queries: {stats['total_cached_queries']}
  • Queries reused: {stats['reused_queries']}
  • API calls saved: {stats['api_calls_saved']}
  • Overall efficiency: {stats['efficiency']}

🏆 Top Performing Queries:
""")

for i, q in enumerate(top_queries[:5], 1):
    print(f"  {i}. {q['query'][:50]}... ({q['reuse_count']} hits)")

print(f"""
💰 Cost Impact:
  • Tokens saved: {stats['api_calls_saved'] * 500:,}
  • Cost reduction: ${(stats['api_calls_saved'] * 500) / 1000 * 0.001:.2f}
  • Users served: ~{(stats['api_calls_saved'] * 500) / 30000:.0f}k
  
📈 Trend:
  • Cache growing: {'Yes' if stats['total_cached_queries'] > 100 else 'Ramping up'}
  • Hit rate acceptable: {'Yes' if stats['efficiency'] else 'Monitor'}
  • Database size: Good
  
✅ Next month recommendations:
  1. If hit rate > 70%: Expand FAQ module
  2. If hit rate < 50%: Lower similarity threshold to 85%
  3. Archive old cache (>60 days) to other table
  4. Monitor top 30 unfound queries → add to FAQ
""")
```

---

## 📈 Key Performance Indicators (KPIs)

### Target Metrics

| KPI | Week 1 | Week 2 | Week 4 | Month 2 |
|-----|--------|--------|--------|----------|
| **Cache entries** | 0-50 | 50-150 | 150-400 | 400+ |
| **Cache hit rate** | 0% | 20% | 50% | 70%+ |
| **API calls/day** | 100 | 80 | 50 | 20 |
| **Tokens/day** | 100K | 80K | 50K | 10K |
| **Quota usage** | 5% | 4% | 2.5% | 0.5% |
| **Users served** | 2K | 2.5K | 4K | 10K |

### Alert Thresholds

```python
# Alert if these conditions are met:

WARNINGS = {
    'cache_not_growing': {
        'condition': 'cache_entries < 50 after 7 days',
        'action': 'Check if API calls are being saved to cache'
    },
    'hit_rate_low': {
        'condition': 'hit_rate < 20% after 2 weeks',
        'action': 'Lower similarity threshold from 90% to 85%'
    },
    'db_too_large': {
        'condition': 'cache_entries > 1000',
        'action': 'Run maintenance: delete entries > 60 days old'
    },
    'quota_usage_high': {
        'condition': 'quota_usage > 70%',
        'action': 'Expand FAQ or increase cache threshold'
    },
}
```

---

## 🔄 Monitoring Automation

### Automated Daily Report (Cron Job)

Create `scripts/daily_monitoring.py`:
```python
#!/usr/bin/env python3
"""Daily monitoring and reporting"""
import datetime
from app.utils.cache_monitor import CacheMonitor
from app.db.database import SessionLocal
from app.utils.logger import log_to_sheets

db = SessionLocal()
monitor = CacheMonitor()

# Get report
report = monitor.get_performance_report(db)

# Log to sheets (for tracking over time)
log_to_sheets(
    event_type="DAILY_OPTIMIZATION_REPORT",
    details={
        'cached_queries': report['cache_stats']['total_cached_queries'],
        'api_calls_saved': report['cache_stats']['api_calls_saved'],
        'efficiency': report['cache_stats']['efficiency'],
        'recommendation': report['status'],
    }
)

print(f"✅ Daily report logged - {datetime.date.today()}")
```

Add to crontab:
```bash
# Run daily at 8 AM
0 8 * * * cd /path/to/bot && python scripts/daily_monitoring.py
```

### Weekly Cleanup (Cron Job)

```bash
# Run every Sunday at 2 AM
0 2 * * 0 cd /path/to/bot && python -c \
  "from app.utils.cache_monitor import CacheMonitor; \
   monitor = CacheMonitor(); \
   monitor.perform_maintenance(days_to_keep=30)"
```

---

## 🚨 Troubleshooting

### Problem: Cache not growing

**Symptoms:**
- Cache entries stay at 0 after 24 hours
- All messages go through API

**Solutions:**
```python
# 1. Check if cache table exists
SELECT COUNT(*) FROM ai_response_cache;

# 2. Check if save_to_cache is being called
grep "Saved new cache" logs/app.log

# 3. Verify no errors
grep "Error saving to cache" logs/app.log

# 4. Check database connection
python -c "from app.db.database import SessionLocal; \
           db = SessionLocal(); \
           print(db.query(AIResponseCache).count())"
```

### Problem: Low cache hit rate

**Symptoms:**
- Only 10-15% cache hit after 1 week
- Expecting 40%+

**Solutions:**
```python
# 1. Lower similarity threshold
cached = find_cached_response(query, db, min_similarity=85)  # was 90

# 2. Check if similarity matching works
from app.utils.cache import calculate_similarity
similarity = calculate_similarity(query1, query2)
# Should show 85%+ for similar queries

# 3. Check cache distribution
monitor.get_top_cached_queries(db, limit=20)
# See if same queries are being repeated
```

### Problem: Database growing too large

**Symptoms:**
- Cache table has 1000+ entries after 1 month
- Database file size increasing

**Solutions:**
```python
# 1. Run cleanup more frequently
monitor.perform_maintenance(db, days_to_keep=14)  # Keep 2 weeks instead

# 2. Archive old data
db.execute("""
    INSERT INTO cache_archive 
    SELECT * FROM ai_response_cache 
    WHERE created_at < DATE_SUB(NOW(), INTERVAL 60 DAY)
""")

# 3. Check storage use
SELECT 
    (data_length + index_length) / 1024 / 1024 AS 'Size (MB)'
FROM information_schema.tables 
WHERE table_name = 'ai_response_cache';
```

---

## ✅ Success Criteria

You'll know it's working when:

**24 Hours:**
- ✅ Cache table has 10+ entries
- ✅ Logs show "Cache HIT" messages
- ✅ No errors related to cache

**1 Week:**
- ✅ Cache has 50+ entries
- ✅ Cache hit rate 15-25%
- ✅ API calls visible reduced
- ✅ Tokens/day trending down

**2 Weeks:**
- ✅ Cache has 150+ entries
- ✅ Cache hit rate 30-40%
- ✅ Quota usage < 5% (down from 5%)
- ✅ Top queries identified

**1 Month:**
- ✅ Cache has 300+ entries
- ✅ Cache hit rate 50%+
- ✅ Quota usage < 2.5%
- ✅ Can serve 4-5K users
- ✅ No database issues

**2 Months:**
- ✅ Cache has 500+ entries
- ✅ Cache hit rate 70%+
- ✅ Quota usage < 1%
- ✅ Can serve 10K users! 🎉

---

## 📞 Support

If you encounter issues:

1. **Check logs:** `tail -f logs/app.log | grep -i cache`
2. **Run report:** `CacheMonitor.get_performance_report(db)`
3. **Verify DB:** `SELECT COUNT(*) FROM ai_response_cache;`
4. **Read guides:** Check `FREE_TIER_OPTIMIZATION_STRATEGY.md`

---

Generated: April 4, 2026
Status: ✅ Ready to Deploy
