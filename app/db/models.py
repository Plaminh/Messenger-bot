"""
SQLAlchemy ORM Models for Vi Vu Danang Chatbot
Based on proposal schema (Phase 1)
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, DECIMAL, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base

class FAQ(Base):
    """FAQ table for rule-based answers"""
    __tablename__ = "faq"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)  # 'gia_ca', 'thu_tuc', 'dich_vu', 'luong_te'
    keywords = Column(Text, nullable=True)  # "giá|bảng giá|bao nhiêu"
    created_at = Column(DateTime, default=datetime.utcnow)

class Vehicle(Base):
    """Vehicles inventory"""
    __tablename__ = "vehicles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    seats = Column(Integer, nullable=False)
    price_per_day_no_driver = Column(DECIMAL, nullable=True)
    price_per_day_with_driver = Column(DECIMAL, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), default='active')  # 'active', 'inactive'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    availabilities = relationship("VehicleAvailability", back_populates="vehicle", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="vehicle")

class VehicleAvailability(Base):
    """Vehicle availability calendar"""
    __tablename__ = "vehicle_availability"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False)
    busy_date = Column(Date, nullable=False)
    status = Column(String(20), default='available')  # 'available', 'booked'
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    vehicle = relationship("Vehicle", back_populates="availabilities")

class Driver(Base):
    """Drivers management"""
    __tablename__ = "drivers"
    
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(15), nullable=True)
    experience_years = Column(Integer, nullable=True)
    status = Column(String(20), default='ready')  # 'ready', 'off', 'busy'
    vehicle_type = Column(String(50), nullable=True)  # '4-seat', '7-seat', '16-seat'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    bookings = relationship("Booking", back_populates="driver")

class Booking(Base):
    """Bookings/Orders"""
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    fb_user_id = Column(String(100), nullable=False, index=True)
    fb_user_name = Column(String(100), nullable=True)
    fb_user_phone = Column(String(15), nullable=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id'), nullable=False)
    driver_id = Column(Integer, ForeignKey('drivers.id', ondelete='SET NULL'), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    pickup_location = Column(String(255), nullable=True)
    dropoff_location = Column(String(255), nullable=True)
    total_price = Column(DECIMAL, nullable=True)
    status = Column(String(20), default='pending')  # 'pending', 'confirmed', 'completed', 'cancelled'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vehicle = relationship("Vehicle", back_populates="bookings")
    driver = relationship("Driver", back_populates="bookings")

class MessageLog(Base):
    """Chat history logs"""
    __tablename__ = "message_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    fb_user_id = Column(String(100), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    message_type = Column(String(20), nullable=True)  # 'text', 'quick_reply', 'button', 'image'
    meta_data = Column(JSON, nullable=True)  # Extra info (button clicked, image URL, etc)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class AIResponseCache(Base):
    """
    Cache for AI responses to reduce API quota usage.
    Uses query hash for fast lookup when similar questions are asked.
    """
    __tablename__ = "ai_response_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    user_query_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_query = Column(Text, nullable=False)  # Store original query for debugging
    ai_answer = Column(Text, nullable=False)
    use_count = Column(Integer, default=1)  # Track reuse frequency for analytics
    similarity_threshold = Column(Integer, default=90)  # Minimum similarity % to use cache
    last_used_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
