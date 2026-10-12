"""Health check API endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker and monitoring."""
    return {"status": "healthy"}
