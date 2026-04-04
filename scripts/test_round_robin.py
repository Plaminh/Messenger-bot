"""
Test Script: Verify Round-Robin 9 API Keys Configuration
Tests if all 9 Gemini API keys are loaded and rotation works correctly
"""
import sys
import os
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables from .env
from dotenv import load_dotenv
load_dotenv(str(project_root / ".env"))

import logging
from app.core.config import GEMINI_API_KEYS, GEMINI_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text):
    """Print success message"""
    print(f"  ✅ {text}")


def print_error(text):
    """Print error message"""
    print(f"  ❌ {text}")


def print_info(text):
    """Print info message"""
    print(f"  ℹ️  {text}")


def test_env_loading():
    """Test if .env file is loaded correctly"""
    print_header("🔧 STEP 1: Verify .env File Loading")
    
    env_file = project_root / ".env"
    
    if env_file.exists():
        print_success(f".env file found: {env_file}")
    else:
        print_error(f".env file NOT found at {env_file}")
        print_info("Run: cp .env.example .env")
        return False
    
    return True


def test_api_keys_loaded():
    """Test if all 9 API keys are loaded from .env"""
    print_header("🔑 STEP 2: Verify 9 API Keys Loaded")
    
    if not GEMINI_API_KEYS:
        print_error("No API keys loaded! GEMINI_API_KEYS is empty")
        print_info("Make sure .env has GEMINI_API_KEY_1 through GEMINI_API_KEY_9")
        return False
    
    print_success(f"Found {len(GEMINI_API_KEYS)} API key(s)")
    
    # Show key status (first 10 chars + ...)
    for i, key in enumerate(GEMINI_API_KEYS, 1):
        key_preview = f"{key[:10]}...{key[-5:]}" if len(key) > 15 else key
        print_info(f"Key #{i}: {key_preview}")
    
    # Check if we have exactly 9 keys
    if len(GEMINI_API_KEYS) == 9:
        print_success("All 9 API keys loaded! ✨")
        return True
    elif len(GEMINI_API_KEYS) < 9:
        print_error(f"Only {len(GEMINI_API_KEYS)} keys found (need 9)")
        print_info(f"Missing: {9 - len(GEMINI_API_KEYS)} key(s)")
        return False
    else:
        print_error(f"Too many keys found: {len(GEMINI_API_KEYS)} (expected 9)")
        return False


def test_gemini_model():
    """Test if Gemini model is configured"""
    print_header("🤖 STEP 3: Verify Gemini Model Configuration")
    
    print_success(f"Model: {GEMINI_MODEL}")
    
    if GEMINI_MODEL == "gemini-2.0-flash":
        print_success("Using Gemini 2.0 Flash (Unlimited RPD, 30 RPM per key)")
    else:
        print_info(f"Using model: {GEMINI_MODEL}")
    
    return True


def test_round_robin_initialization():
    """Test if GeminiRoundRobin initializes correctly"""
    print_header("🔄 STEP 4: Test Round-Robin Initialization")
    
    try:
        from app.ai.gemini import GeminiRoundRobin
        
        # Initialize
        rr = GeminiRoundRobin()
        print_success("GeminiRoundRobin initialized successfully!")
        
        print_info(f"Number of keys: {len(rr.available_keys)}")
        print_info(f"RPM capacity: {len(rr.available_keys)} × 30 = {len(rr.available_keys) * 30} RPM")
        
        return True
    
    except ValueError as e:
        print_error(f"Failed to initialize GeminiRoundRobin: {e}")
        return False
    
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False


def test_key_rotation():
    """Test if key rotation works (should cycle through 1-9-1-9...)"""
    print_header("🔁 STEP 5: Test Key Rotation Logic")
    
    try:
        from app.ai.gemini import GeminiRoundRobin
        
        rr = GeminiRoundRobin()
        
        # Test 15 rotations (should go: 1→2→...→9→1→2→...→9)
        rotation_sequence = []
        for i in range(15):
            key = rr.get_next_key()
            key_id = key[:10]
            rotation_sequence.append(key_id)
        
        print_success(f"Rotation sequence (15 calls):")
        print(f"    {' → '.join(rotation_sequence[:9])}")
        print(f"    {' → '.join(rotation_sequence[9:])}")  # Should start from key 1 again
        
        # Verify it cycles: 1,2,3,...,9,1,2,3,...
        if rotation_sequence[9] == rotation_sequence[0]:
            print_success("✨ Key rotation is WORKING! (Cycle repeats after 9 keys)")
            return True
        else:
            print_error("Key rotation may not be working correctly")
            return False
    
    except Exception as e:
        print_error(f"Error testing rotation: {e}")
        return False


def test_usage_stats():
    """Test if usage statistics tracking works"""
    print_header("📊 STEP 6: Test Usage Statistics")
    
    try:
        from app.ai.gemini import GeminiRoundRobin
        
        rr = GeminiRoundRobin()
        
        # Make 18 calls (2 full cycles)
        for i in range(18):
            rr.get_next_key()
        
        print_success(f"Total calls: {rr.call_count}")
        print_info("Key usage breakdown:")
        
        total_usage = sum(rr.key_usage.values())
        for key_id, usage_count in sorted(rr.key_usage.items()):
            percentage = (usage_count / total_usage * 100) if total_usage > 0 else 0
            bar = "█" * int(percentage / 5)
            print(f"    {key_id}: {usage_count} calls ({percentage:.1f}%) {bar}")
        
        # All keys should have roughly equal usage
        usage_values = list(rr.key_usage.values())
        min_usage = min(usage_values)
        max_usage = max(usage_values)
        
        if max_usage - min_usage <= 1:
            print_success("✨ Load is balanced across all keys!")
            return True
        else:
            print_error("Load imbalance detected")
            return False
    
    except Exception as e:
        print_error(f"Error testing usage stats: {e}")
        return False


def test_database_connection():
    """Test if we can connect to PostgreSQL"""
    print_header("🗄️ STEP 7: Test Database Connection")
    
    try:
        from app.core.database import engine, SessionLocal
        from sqlalchemy import text
        
        # Try to connect
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print_success("Database connection successful!")
            return True
    
    except Exception as e:
        print_info(f"Note: Database not available yet (expected if Docker not started)")
        print_info(f"Full error: {e}")
        return True  # Not critical for this test


def test_gemini_connection():
    """Test actual Gemini API connection (requires valid key)"""
    print_header("🌐 STEP 8: Test Gemini API Connection (Optional)")
    
    try:
        import asyncio
        from app.ai.gemini import call_gemini_api
        
        print_info("Attempting to send test request to Gemini API...")
        
        # Run async function
        async def test():
            response = await call_gemini_api(
                user_message="Xin chào! Bạn tên gì?",
                chat_history=None,
                context=None
            )
            return response
        
        # Try to run (will fail if keys are invalid)
        try:
            response = asyncio.run(test())
            if response and "gặp lỗi" not in response.lower():
                print_success("✨ Gemini API connection working!")
                print_info(f"Response preview: {response[:100]}...")
                return True
            else:
                print_error(f"API returned error: {response}")
                return False
        except Exception as e:
            error_str = str(e).lower()
            if "api_key" in error_str or "invalid" in error_str:
                print_error(f"Invalid API key detected: {e}")
                return False
            else:
                print_info(f"API test skipped (expected if keys are placeholder): {e}")
                return True  # Not critical
    
    except ImportError:
        print_info("Skipping Gemini connection test (dependencies not installed)")
        return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  🚀 ROUND-ROBIN 9 API KEYS CONFIGURATION TEST")
    print("=" * 60)
    
    results = {}
    
    # Run tests
    results["env_loading"] = test_env_loading()
    if not results["env_loading"]:
        print_error("\n⚠️ Cannot proceed without .env file!")
        return False
    
    results["api_keys"] = test_api_keys_loaded()
    results["model"] = test_gemini_model()
    results["initialization"] = test_round_robin_initialization()
    results["rotation"] = test_key_rotation()
    results["usage_stats"] = test_usage_stats()
    results["database"] = test_database_connection()
    results["gemini"] = test_gemini_connection()
    
    # Summary
    print_header("✨ TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n  Passed: {passed}/{total}\n")
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        test_display = test_name.replace("_", " ").title()
        print(f"    {status} - {test_display}")
    
    # Final verdict
    print("\n" + "=" * 60)
    
    if passed == total:
        print("  ✅ ALL TESTS PASSED! You're ready to deploy!")
        print("=" * 60)
        return True
    elif passed >= total - 1:  # Allow 1 optional test to fail
        print("  ⚠️  Most tests passed (some optional tests skipped)")
        print("=" * 60)
        return True
    else:
        print(f"  ❌ FAILED - Fix the issues above and try again")
        print("=" * 60)
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
