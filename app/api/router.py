"""
API Router - Manages all v1 endpoints for Phase 1
"""
from fastapi import APIRouter

# Import route modules
from app.api.v1 import vehicles, faqs

api_router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include v1 routes
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(faqs.router, prefix="/faqs", tags=["faqs"])

# Health check endpoint
@api_router.get("/health")
def api_health():
    return {"status": "ok", "service": "Vi Vu Danang API v1"}
