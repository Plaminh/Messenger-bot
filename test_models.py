#!/usr/bin/env python3
"""List available Gemini models"""
import google.generativeai as genai
from app.core.config import GEMINI_API_KEY

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY not set!")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

try:
    models = list(genai.list_models())
    print("\n✅ Available Gemini Models:")
    print("-" * 50)
    for m in models:
        if 'gemini' in m.name.lower():
            print(f"  • {m.name}")
    print("-" * 50)
except Exception as e:
    print(f"❌ Error: {e}")
