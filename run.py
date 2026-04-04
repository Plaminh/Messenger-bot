#!/usr/bin/env python3
"""
Simple ASGI startup script for Render deployment.
Handles Python path setup and starts Uvicorn.
"""
import sys
import os
from pathlib import Path

# Load environment variables from .env file FIRST
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Get the app directory (parent of parent of this script's parent)
# Script should be at /app/run.py
# So /app is at Path(__file__).parent
app_dir = str(Path(__file__).parent)

# Ensure /app is in Python path BEFORE any other imports
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

print(f"✓ Python version: {sys.version}")
print(f"✓ App directory: {app_dir}")
print(f"✓ sys.path: {sys.path[:3]}")
print(f"✓ CWD: {os.getcwd()}")
print()

# Now import and start uvicorn
import uvicorn

if __name__ == "__main__":
    print("Starting Uvicorn server...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
