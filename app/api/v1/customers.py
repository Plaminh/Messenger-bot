"""
Customer Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.database import get_db
from db import crud, schemas, models
from typing import List

router = APIRouter()

# ─── Get all customers ───────────────────────────────────────────
@router.get("/", response_model=List[schemas.CustomerResponse])
def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get all customers (paginated)"""
    return crud.get_customers(db, skip=skip, limit=limit)

# ─── Get customer by ID ──────────────────────────────────────────
@router.get("/{customer_id}", response_model=schemas.CustomerResponse)
def get_customer_by_id(customer_id: int, db: Session = Depends(get_db)):
    """Get customer by ID"""
    customer = crud.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

# ─── Get customer by Facebook ID ─────────────────────────────────
@router.get("/facebook/{facebook_id}", response_model=schemas.CustomerResponse)
def get_customer_by_facebook(facebook_id: str, db: Session = Depends(get_db)):
    """Get customer by Facebook ID"""
    customer = crud.get_customer_by_facebook_id(db, facebook_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

# ─── Create customer ────────────────────────────────────────────
@router.post("/", response_model=schemas.CustomerResponse)
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    """Create new customer"""
    # Check if customer already exists
    existing = crud.get_customer_by_facebook_id(db, customer.facebook_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Customer with Facebook ID {customer.facebook_id} already exists"
        )
    return crud.create_customer(db, customer)

# ─── Update customer ────────────────────────────────────────────
@router.put("/{customer_id}", response_model=schemas.CustomerResponse)
def update_customer(
    customer_id: int,
    customer: schemas.CustomerUpdate,
    db: Session = Depends(get_db)
):
    """Update customer"""
    updated = crud.update_customer(db, customer_id, customer)
    if not updated:
        raise HTTPException(status_code=404, detail="Customer not found")
    return updated

# ─── Delete customer ────────────────────────────────────────────
@router.delete("/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """Delete customer"""
    success = crud.delete_customer(db, customer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"message": "Customer deleted"}

# ─── Get customer conversation history ───────────────────────────
@router.get("/{customer_id}/conversations", response_model=List[schemas.ConversationResponse])
def get_customer_conversations(
    customer_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get all conversations for a customer"""
    customer = crud.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return crud.get_conversations(db, customer_id=customer_id, skip=skip, limit=limit)
