"""
Route Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.db import crud, schemas
from typing import List

router = APIRouter()

# ─── Get all routes ─────────────────────────────────────────────
@router.get("/", response_model=List[schemas.RouteResponse])
def list_routes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get all routes"""
    return crud.get_routes(db, skip=skip, limit=limit)

# ─── Get route by ID ────────────────────────────────────────────
@router.get("/{route_id}", response_model=schemas.RouteResponse)
def get_route(route_id: int, db: Session = Depends(get_db)):
    """Get route by ID"""
    route = crud.get_route(db, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route

# ─── Create route ───────────────────────────────────────────────
@router.post("/", response_model=schemas.RouteResponse)
def create_route(route: schemas.RouteCreate, db: Session = Depends(get_db)):
    """Create new route"""
    return crud.create_route(db, route)

# ─── Delete route ───────────────────────────────────────────────
@router.delete("/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db)):
    """Delete route"""
    success = crud.delete_route(db, route_id)
    if not success:
        raise HTTPException(status_code=404, detail="Route not found")
    return {"message": "Route deleted"}
