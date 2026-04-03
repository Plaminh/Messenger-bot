"""
Configuration & Environment Variables
"""
import os
from typing import Optional

# ─── Database ────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:dev_password_123@db:5432/vi_vu_danang"
)

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "dev_password_123")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "vi_vu_danang")

SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "False").lower() == "true"

# ─── Meta Messenger ──────────────────────────────────────────────
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "your_verify_token_here")
META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "your_page_token_here")
META_API_VERSION = os.getenv("META_API_VERSION", "v18.0")

# ─── Gemini AI ───────────────────────────────────────────────────
# Choose: 'ai_studio' (free, limited) or 'vertex_ai' (Google Cloud, uses credits)
GEMINI_API_TYPE = os.getenv("GEMINI_API_TYPE", "ai_studio")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

# ─── Google Cloud (for Vertex AI) ────────────────────────────────
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")  # Your GCP project ID
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")  # Vertex AI region

# ─── Server ──────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# ─── App Settings ────────────────────────────────────────────────
APP_NAME = os.getenv("APP_NAME", "Vi Vu Danang Chatbot")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

# ─── Logging ──────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
