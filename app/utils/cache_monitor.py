"""
Cache Monitor and Maintenance
Provides utilities for monitoring cache performance and maintaining database health
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db import models
from app.utils.cache import get_cache_stats, clear_old_cache

logger = logging.getLogger(__name__)


class CacheMonitor:
    """
    Monitor cache performance and provide optimization insights
    """
    
    @staticmethod
    def get_performance_report(db: Session) -> dict:
        """
        Get detailed cache performance report
        
        Returns:
            Dictionary with cache metrics and recommendations
        """
        try:
            stats = get_cache_stats(db)
            total_entries = db.query(models.AIResponseCache).count()
            
            # Calculate additional metrics
            high_use_entries = db.query(models.AIResponseCache).filter(
                models.AIResponseCache.use_count >= 3
            ).count()
            
            # Calculate average response length
            avg_response_length = db.query(
                db.func.avg(db.func.length(models.AIResponseCache.ai_answer))
            ).scalar() or 0
            
            # Calculate database size impact
            total_query_chars = db.query(
                db.func.sum(db.func.length(models.AIResponseCache.user_query))
            ).scalar() or 0
            
            total_answer_chars = db.query(
                db.func.sum(db.func.length(models.AIResponseCache.ai_answer))
            ).scalar() or 0
            
            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "cache_stats": stats,
                "metrics": {
                    "total_cached_queries": total_entries,
                    "high_use_entries": high_use_entries,
                    "avg_response_length": f"{avg_response_length:.0f} characters",
                    "total_storage": f"{(total_query_chars + total_answer_chars) / 1024:.2f} KB"
                },
                "recommendations": []
            }
            
            # Generate recommendations
            if total_entries > 500:
                report["recommendations"].append(
                    "⚠️ Cache size is large (>500 entries). Consider running maintenance."
                )
            
            if stats.get("api_calls_saved", 0) < 10:
                report["recommendations"].append(
                    "ℹ️ Cache has saved less than 10 API calls. Give it more time to build up."
                )
            
            if high_use_entries < total_entries * 0.1:
                report["recommendations"].append(
                    "ℹ️ Most cached queries are rarely reused. Consider FAQ expansion instead."
                )
            
            efficiency = float(stats.get("efficiency", "0%").rstrip("%"))
            if efficiency > 50:
                report["status"] = "✅ Cache is performing very well!"
            elif efficiency > 20:
                report["status"] = "⚠️ Cache is active but could be better."
            else:
                report["status"] = "ℹ️ Cache is still building up."
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_top_cached_queries(db: Session, limit: int = 10) -> list[dict]:
        """
        Get most frequently used cached queries
        
        Args:
            db: Database session
            limit: Number of top queries to return
            
        Returns:
            List of top cached queries with use counts
        """
        try:
            top_queries = db.query(
                models.AIResponseCache.user_query,
                models.AIResponseCache.use_count,
                models.AIResponseCache.last_used_at
            ).order_by(
                models.AIResponseCache.use_count.desc()
            ).limit(limit).all()
            
            return [
                {
                    "query": q[0],
                    "reuse_count": q[1],
                    "last_used": q[2].isoformat() if q[2] else None
                }
                for q in top_queries
            ]
        except Exception as e:
            logger.error(f"Error getting top cached queries: {e}")
            return []
    
    @staticmethod
    def perform_maintenance(db: Session, days_to_keep: int = 30) -> dict:
        """
        Perform cache maintenance (cleanup old entries)
        
        Args:
            db: Database session
            days_to_keep: Keep only entries from last N days
            
        Returns:
            Dictionary with maintenance results
        """
        try:
            # Get stats before
            stats_before = get_cache_stats(db)
            
            # Delete old entries
            deleted_count = clear_old_cache(days_to_keep, db)
            
            # Get stats after
            stats_after = get_cache_stats(db)
            
            return {
                "success": True,
                "deleted_entries": deleted_count,
                "days_kept": days_to_keep,
                "before": stats_before,
                "after": stats_after,
                "message": f"Deleted {deleted_count} cache entries older than {days_to_keep} days"
            }
        except Exception as e:
            logger.error(f"Error during maintenance: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def export_cache_data(db: Session, output_format: str = "json") -> dict | str:
        """
        Export cache data for analysis
        
        Args:
            db: Database session
            output_format: 'json' or 'csv'
            
        Returns:
            Exported cache data in requested format
        """
        try:
            import json
            
            cache_entries = db.query(models.AIResponseCache).all()
            
            data = [
                {
                    "id": entry.id,
                    "query": entry.user_query,
                    "answer_length": len(entry.ai_answer),
                    "use_count": entry.use_count,
                    "created_at": entry.created_at.isoformat(),
                    "last_used_at": entry.last_used_at.isoformat() if entry.last_used_at else None
                }
                for entry in cache_entries
            ]
            
            if output_format == "json":
                return json.dumps(data, ensure_ascii=False, indent=2)
            elif output_format == "csv":
                import csv
                from io import StringIO
                output = StringIO()
                if data:
                    writer = csv.DictWriter(output, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                return output.getvalue()
            
            return data
            
        except Exception as e:
            logger.error(f"Error exporting cache data: {e}")
            return {"error": str(e)}


# Convenience functions for CLI/admin tools
def print_cache_report(db: Session) -> None:
    """Print cache performance report to console"""
    monitor = CacheMonitor()
    report = monitor.get_performance_report(db)
    
    print("\n" + "="*60)
    print("📊 CACHE PERFORMANCE REPORT")
    print("="*60)
    print(f"Timestamp: {report.get('timestamp')}")
    print(f"Status: {report.get('status')}")
    
    if "metrics" in report:
        print("\n📈 Metrics:")
        for key, value in report["metrics"].items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
    
    if "cache_stats" in report:
        print("\n💾 Cache Stats:")
        for key, value in report["cache_stats"].items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
    
    if report.get("recommendations"):
        print("\n💡 Recommendations:")
        for rec in report["recommendations"]:
            print(f"  {rec}")
    
    print("\n" + "="*60)


def print_top_queries(db: Session, limit: int = 10) -> None:
    """Print top cached queries to console"""
    monitor = CacheMonitor()
    top_queries = monitor.get_top_cached_queries(db, limit)
    
    print("\n" + "="*60)
    print(f"🔥 TOP {limit} CACHED QUERIES")
    print("="*60)
    
    for i, query_info in enumerate(top_queries, 1):
        print(f"\n{i}. Reuse Count: {query_info['reuse_count']}")
        print(f"   Query: {query_info['query'][:80]}...")
        print(f"   Last Used: {query_info['last_used']}")
    
    print("\n" + "="*60)
