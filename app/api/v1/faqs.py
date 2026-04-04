"""
FAQ API Endpoints (Phase 1)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.database import get_db
from db import crud, schemas
from typing import List

router = APIRouter()

@router.get("/", response_model=List[schemas.FAQResponse])
def list_faqs(
    category: str = Query(None),
    db: Session = Depends(get_db)
):
    """Get all FAQs (optionally filter by category)"""
    return crud.get_all_faqs(db, category=category)

@router.get("/{faq_id}", response_model=schemas.FAQResponse)
def get_faq(faq_id: int, db: Session = Depends(get_db)):
    """Get FAQ by ID"""
    faq = crud.get_faq(db, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return faq

# ─── Create FAQ ─────────────────────────────────────────────────
@router.post("/", response_model=schemas.FAQResponse)
def create_faq(faq: schemas.FAQCreate, db: Session = Depends(get_db)):
    """Create new FAQ"""
    return crud.create_faq(db, faq)

# ─── Update FAQ ─────────────────────────────────────────────────
@router.put("/{faq_id}", response_model=schemas.FAQResponse)
def update_faq(
    faq_id: int,
    faq: schemas.FAQUpdate,
    db: Session = Depends(get_db)
):
    """Update FAQ"""
    updated = crud.update_faq(db, faq_id, faq)
    if not updated:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return updated

# ─── Delete FAQ ─────────────────────────────────────────────────
@router.delete("/{faq_id}")
def delete_faq(faq_id: int, db: Session = Depends(get_db)):
    """Delete FAQ"""
    success = crud.delete_faq(db, faq_id)
    if not success:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"message": "FAQ deleted"}
