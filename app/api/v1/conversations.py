"""
Conversation Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.db import crud, schemas
from typing import List

router = APIRouter()

# ─── Get all conversations ──────────────────────────────────────
@router.get("/", response_model=List[schemas.ConversationResponse])
def list_conversations(
    customer_id: int = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get all conversations (optionally filter by customer)"""
    return crud.get_conversations(db, customer_id=customer_id, skip=skip, limit=limit)

# ─── Get conversation by ID ─────────────────────────────────────
@router.get("/{conversation_id}", response_model=schemas.ConversationResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Get conversation by ID"""
    conv = crud.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

# ─── Create conversation (log new message) ──────────────────────
@router.post("/", response_model=schemas.ConversationResponse)
def create_conversation(
    conversation: schemas.ConversationCreate,
    db: Session = Depends(get_db)
):
    """Create new conversation (log a message + response)"""
    return crud.create_conversation(db, conversation)

# ─── Delete conversation ────────────────────────────────────────
@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Delete conversation"""
    success = crud.delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}
