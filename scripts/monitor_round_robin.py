#!/usr/bin/env python3
"""
Round-Robin API Key Monitoring Script
Tracks API key usage and quota statistics
"""
import asyncio
import datetime
from app.ai.gemini import get_key_usage_stats
from app.db.database import SessionLocal
from app.db import models
from sqlalchemy import func

def print_header(title: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_stats(stats: dict):
    """Print API key usage statistics"""
    if not stats or not stats.get('total_calls'):
        print("ℹ️  No API calls made yet")
        return
    
    print(f"""
📊 API KEY STATISTICS
────────────────────────────────────────────────────
Total API calls made:     {stats['total_calls']:,}
Number of keys:           {stats['num_keys']}
RPM capacity:             {stats['rpm_capacity']} requests/minute
Avg calls per key:        {stats['total_calls'] // stats['num_keys']}

🔑 PER-KEY BREAKDOWN:
""")
    
    key_usage = stats.get('key_usage', {})
    if key_usage:
        total = sum(key_usage.values())
        for i, (key_id, count) in enumerate(sorted(key_usage.items(), key=lambda x: -x[1]), 1):
            pct = (count / total * 100) if total > 0 else 0
            bar_width = 40
            filled = int(bar_width * count / max(key_usage.values()))
            bar = "█" * filled + "░" * (bar_width - filled)
            print(f"  Key #{i} ({key_id}...): {count:>5} calls ({pct:>5.1f}%) {bar}")

def get_cache_stats(db):
    """Get cache hit statistics"""
    try:
        total = db.query(func.count(models.AIResponseCache.id)).scalar() or 0
        high_use = db.query(models.AIResponseCache).filter(
            models.AIResponseCache.use_count >= 3
        ).count()
        
        return {
            'total_cached': total,
            'high_use_entries': high_use
        }
    except Exception as e:
        print(f"⚠️  Error getting cache stats: {e}")
        return {}

def get_message_stats(db):
    """Get message statistics"""
    try:
        # Assuming MessageLog table exists
        total_messages = db.query(func.count(models.MessageLog.id)).scalar() or 0
        return {'total_messages': total_messages}
    except:
        # MessageLog might not exist in all setups
        return {}

def print_quota_efficiency():
    """Calculate and print quota efficiency"""
    try:
        stats = get_key_usage_stats()
        
        if not stats or not stats.get('total_calls'):
            print("ℹ️  No API calls yet - cannot calculate efficiency")
            return
        
        total_calls = stats['total_calls']
        monthly_estimate = total_calls * 30  # Rough estimate
        quota_per_key = 60000  # Default free tier
        
        print(f"""
📈 QUOTA EFFICIENCY
────────────────────────────────────────────────────
Total API calls (all time): {total_calls:,}
Estimated monthly calls:    {monthly_estimate:,}
Quota per key:              {quota_per_key:,}
Total quota available:      {quota_per_key * stats['num_keys']:,}
Estimated usage:            {(monthly_estimate / (quota_per_key * stats['num_keys']) * 100):.1f}%

✅ Status: {'EXCELLENT' if (monthly_estimate / (quota_per_key * stats['num_keys']) * 100) < 50 else 'GOOD' if (monthly_estimate / (quota_per_key * stats['num_keys']) * 100) < 80 else 'MONITOR'}
""")
    except Exception as e:
        print(f"⚠️  Error calculating efficiency: {e}")

def print_combined_stats():
    """Print combined statistics from all layers"""
    print_header("🔄 ROUND-ROBIN MONITORING DASHBOARD")
    
    # API stats
    stats = get_key_usage_stats()
    print_stats(stats)
    
    # Cache stats
    db = SessionLocal()
    try:
        cache_stats = get_cache_stats(db)
        if cache_stats:
            print(f"""
💾 CACHE STATISTICS
────────────────────────────────────────────────────
Cached responses:         {cache_stats.get('total_cached', 0):,}
High-use entries (≥3 hits): {cache_stats.get('high_use_entries', 0):,}
""")
    finally:
        db.close()
    
    # Quota efficiency
    print_quota_efficiency()
    
    # Summary
    print(f"""
⏰ Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📝 Tip: Run this script daily to monitor performance

""")

if __name__ == "__main__":
    try:
        print_combined_stats()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
