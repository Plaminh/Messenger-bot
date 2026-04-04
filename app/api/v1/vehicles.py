"""
Vehicles API Endpoints (Phase 1)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from db import crud, schemas
from typing import List

router = APIRouter()

@router.get("/", response_model=List[schemas.VehicleResponse])
def get_all_vehicles(db: Session = Depends(get_db)):
    """Get all available vehicles"""
    vehicles = crud.get_all_vehicles(db, status='active')
    return vehicles

@router.get("/{vehicle_id}", response_model=schemas.VehicleResponse)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Get vehicle by ID"""
    vehicle = crud.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle

# ─── Delete vehicle ─────────────────────────────────────────────
@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Delete vehicle"""
    success = crud.delete_vehicle(db, vehicle_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return {"message": "Vehicle deleted"}
