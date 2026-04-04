#!/bin/bash
# Startup script to ensure proper Python path and import resolution

set -e

echo "Starting Vi Vu Danang Chatbot..."
echo "Python version: $(python --version)"
echo "PYTHONPATH: $PYTHONPATH"
echo "Working directory: $(pwd)"
echo ""

# Verify app directory structure
if [ ! -d "/app/app" ]; then
    echo "ERROR: /app/app directory not found!"
    ls -la /app/
    exit 1
fi

if [ ! -f "/app/app/main.py" ]; then
    echo "ERROR: /app/app/main.py not found!"
    ls -la /app/app/
    exit 1
fi

if [ ! -f "/app/app/core/config.py" ]; then
    echo "ERROR: /app/app/core/config.py not found!"
    ls -la /app/app/core/
    exit 1
fi

echo "✓ Project structure verified"
echo "✓ app/main.py found"
echo "✓ app/core/config.py found"
echo ""

# Run uvicorn with explicit Python module invocation
echo "Starting uvicorn server..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
