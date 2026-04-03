"""
Pydantic Schemas for Request/Response Validation
Based on proposal models
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal

# ─── FAQ Schemas ────────────────────────────────────────────────

class FAQCreate(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None
    keywords: Optional[str] = None

class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    keywords: Optional[str] = None

class FAQResponse(BaseModel):
    id: int
    question: str
    answer: str
    category: Optional[str]
    keywords: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ─── Vehicle Schemas ────────────────────────────────────────────

class VehicleCreate(BaseModel):
    name: str
    seats: int
    price_per_day_no_driver: Optional[Decimal] = None
    price_per_day_with_driver: Optional[Decimal] = None
    description: Optional[str] = None
    status: str = 'active'

class VehicleUpdate(BaseModel):
    name: Optional[str] = None
    seats: Optional[int] = None
    price_per_day_no_driver: Optional[Decimal] = None
    price_per_day_with_driver: Optional[Decimal] = None
    description: Optional[str] = None
    status: Optional[str] = None

class VehicleResponse(BaseModel):
    id: int
    name: str
    seats: int
    price_per_day_no_driver: Optional[Decimal]
    price_per_day_with_driver: Optional[Decimal]
    description: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ─── Driver Schemas ─────────────────────────────────────────────

class DriverCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    experience_years: Optional[int] = None
    status: str = 'ready'
    vehicle_type: Optional[str] = None

class DriverUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    experience_years: Optional[int] = None
    status: Optional[str] = None
    vehicle_type: Optional[str] = None

class DriverResponse(BaseModel):
    id: int
    full_name: str
    phone: Optional[str]
    experience_years: Optional[int]
    status: str
    vehicle_type: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ─── Booking Schemas ────────────────────────────────────────────

class BookingCreate(BaseModel):
    fb_user_id: str
    fb_user_name: Optional[str] = None
    fb_user_phone: Optional[str] = None
    vehicle_id: int
    driver_id: Optional[int] = None
    start_date: date
    end_date: date
    pickup_location: Optional[str] = None
    dropoff_location: Optional[str] = None
    total_price: Optional[Decimal] = None
    notes: Optional[str] = None

class BookingUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class BookingResponse(BaseModel):
    id: int
    fb_user_id: str
    fb_user_name: Optional[str]
    fb_user_phone: Optional[str]
    vehicle_id: int
    driver_id: Optional[int]
    start_date: date
    end_date: date
    pickup_location: Optional[str]
    dropoff_location: Optional[str]
    total_price: Optional[Decimal]
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ─── Message Log Schemas ────────────────────────────────────────

class MessageLogCreate(BaseModel):
    fb_user_id: str
    role: str
    content: str
    message_type: Optional[str] = None
    metadata: Optional[dict] = None

class MessageLogResponse(BaseModel):
    id: int
    fb_user_id: str
    role: str
    content: str
    message_type: Optional[str]
    metadata: Optional[dict]
    created_at: datetime
    
    class Config:
        from_attributes = True
