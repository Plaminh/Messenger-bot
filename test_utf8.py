"""Test with proper UTF-8 encoding"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'))

from app.handlers.router import MessageRouter
from app.core.database import SessionLocal
import asyncio
import logging

# Only show critical errors
logging.basicConfig(level=logging.CRITICAL)

async def test():
    db = SessionLocal()
    result = await MessageRouter.route_message('Gia xe bao nhieu?', 'user1', db)
    # Show result without Vietnamese characters in first line
    print(f"Result length: {len(result)} characters")
    print(f"First 100 chars: {result[:100]}")
    print(f"\nFull response:\n{result}")
    db.close()

print("Testing bot response...")
print("-" * 60)
asyncio.run(test())
