"""
CRUD Operations - Phase 1 - Vi Vu Danang
"""
from sqlalchemy.orm import Session
from app.db import models, schemas
from typing import List, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# FAQ CRUD
# ═══════════════════════════════════════════════════════════════════

def get_faq(db: Session, faq_id: int) -> Optional[models.FAQ]:
    """Get FAQ by ID"""
    return db.query(models.FAQ).filter(models.FAQ.id == faq_id).first()

def get_all_faqs(db: Session, category: Optional[str] = None) -> List[models.FAQ]:
    """Get all FAQs"""
    query = db.query(models.FAQ)
    if category:
        query = query.filter(models.FAQ.category == category)
    return query.all()

def create_faq(db: Session, faq_data: schemas.FAQCreate) -> Optional[models.FAQ]:
    """Create new FAQ"""
    try:
        faq = models.FAQ(**faq_data.dict())
        db.add(faq)
        db.commit()
        db.refresh(faq)
        logger.info(f"✅ FAQ created: {faq.id}")
        return faq
    except Exception as e:
        logger.error(f"Error creating FAQ: {e}")
        db.rollback()
        return None

# ═══════════════════════════════════════════════════════════════════
# VEHICLE CRUD
# ═══════════════════════════════════════════════════════════════════

def get_vehicle(db: Session, vehicle_id: int) -> Optional[models.Vehicle]:
    """Get vehicle by ID"""
    return db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()

def get_all_vehicles(db: Session, status: str = 'active') -> List[models.Vehicle]:
    """Get all active vehicles"""
    return db.query(models.Vehicle).filter(models.Vehicle.status == status).all()

def create_vehicle(db: Session, vehicle_data: schemas.VehicleCreate) -> Optional[models.Vehicle]:
    """Create new vehicle"""
    try:
        vehicle = models.Vehicle(**vehicle_data.dict())
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        logger.info(f"✅ Vehicle created: {vehicle.id}")
        return vehicle
    except Exception as e:
        logger.error(f"Error creating vehicle: {e}")
        db.rollback()
        return None

# ═══════════════════════════════════════════════════════════════════
# VEHICLE AVAILABILITY CRUD
# ═══════════════════════════════════════════════════════════════════

def get_vehicle_availability(db: Session, vehicle_id: int, target_date: date) -> Optional[models.VehicleAvailability]:
    """Check if vehicle is available on specific date"""
    return db.query(models.VehicleAvailability).filter(
        models.VehicleAvailability.vehicle_id == vehicle_id,
        models.VehicleAvailability.busy_date == target_date
    ).first()

def create_availability_record(db: Session, vehicle_id: int, busy_date: date, status: str = 'booked') -> Optional[models.VehicleAvailability]:
    """Create availability record (mark vehicle busy)"""
    try:
        record = models.VehicleAvailability(vehicle_id=vehicle_id, busy_date=busy_date, status=status)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception as e:
        logger.error(f"Error creating availability record: {e}")
        db.rollback()
        return None

# ═══════════════════════════════════════════════════════════════════
# DRIVER CRUD
# ═══════════════════════════════════════════════════════════════════

def get_driver(db: Session, driver_id: int) -> Optional[models.Driver]:
    """Get driver by ID"""
    return db.query(models.Driver).filter(models.Driver.id == driver_id).first()

def get_available_drivers(db: Session) -> List[models.Driver]:
    """Get all available drivers"""
    return db.query(models.Driver).filter(models.Driver.status == 'available').all()

# ═══════════════════════════════════════════════════════════════════
# BOOKING CRUD
# ═══════════════════════════════════════════════════════════════════

def get_booking(db: Session, booking_id: int) -> Optional[models.Booking]:
    """Get booking by ID"""
    return db.query(models.Booking).filter(models.Booking.id == booking_id).first()

def get_user_bookings(db: Session, fb_user_id: str) -> List[models.Booking]:
    """Get all bookings by user"""
    return db.query(models.Booking).filter(
        models.Booking.fb_user_id == fb_user_id
    ).order_by(models.Booking.created_at.desc()).all()

def create_booking(db: Session, booking_data: schemas.BookingCreate) -> Optional[models.Booking]:
    """Create new booking"""
    try:
        booking = models.Booking(**booking_data.dict())
        db.add(booking)
        db.commit()
        db.refresh(booking)
        logger.info(f"✅ Booking created: {booking.id}")
        return booking
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        db.rollback()
        return None

def update_booking(db: Session, booking_id: int, status: str) -> Optional[models.Booking]:
    """Update booking status"""
    try:
        booking = get_booking(db, booking_id)
        if not booking:
            return None
        booking.status = status
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking
    except Exception as e:
        logger.error(f"Error updating booking: {e}")
        db.rollback()
        return None

# ═══════════════════════════════════════════════════════════════════
# MESSAGE_LOG CRUD
# ═══════════════════════════════════════════════════════════════════

def create_message_log(db: Session, fb_user_id: str, role: str, content: str, message_type: str = 'text') -> Optional[models.MessageLog]:
    """Create message log"""
    try:
        msg = models.MessageLog(
            fb_user_id=fb_user_id,
            role=role,
            content=content,
            message_type=message_type
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg
    except Exception as e:
        logger.error(f"Error logging message: {e}")
        db.rollback()
        return None

def get_user_chat_history(db: Session, fb_user_id: str, limit: int = 10) -> List[models.MessageLog]:
    """Get chat history for user (last N messages)"""
    return db.query(models.MessageLog).filter(
        models.MessageLog.fb_user_id == fb_user_id
    ).order_by(models.MessageLog.created_at.desc()).limit(limit).all()
