"""
Booking Handler
Multi-step booking flow
"""
import logging
from datetime import date
from sqlalchemy.orm import Session
from db import models, schemas

logger = logging.getLogger(__name__)

class BookingHandler:
    """
    Handle multi-step booking flow
    """
    
    @staticmethod
    def validate_booking(
        vehicle_id: int,
        start_date: date,
        end_date: date,
        db: Session
    ) -> tuple[bool, str]:
        """
        Validate booking request
        Returns (is_valid, message)
        """
        # Check vehicle exists
        vehicle = db.query(models.Vehicle).filter(
            models.Vehicle.id == vehicle_id
        ).first()
        
        if not vehicle:
            return False, "Xe không tồn tại."
        
        # Check dates are valid
        if start_date > end_date:
            return False, "Ngày bắt đầu phải trước ngày kết thúc."
        
        if start_date < date.today():
            return False, "Ngày bắt đầu phải từ hôm nay trở đi."
        
        return True, "OK"
    
    @staticmethod
    def create_booking(
        booking_data: schemas.BookingCreate,
        db: Session
    ) -> models.Booking | None:
        """
        Create new booking in database
        """
        try:
            # Validate first
            is_valid, msg = BookingHandler.validate_booking(
                booking_data.vehicle_id,
                booking_data.start_date,
                booking_data.end_date,
                db
            )
            
            if not is_valid:
                logger.warning(f"Booking validation failed: {msg}")
                return None
            
            # Calculate total price if not provided
            total_price = booking_data.total_price
            if not total_price:
                vehicle = db.query(models.Vehicle).get(booking_data.vehicle_id)
                days = (booking_data.end_date - booking_data.start_date).days + 1
                if booking_data.driver_id:
                    total_price = vehicle.price_per_day_with_driver * days
                else:
                    total_price = vehicle.price_per_day_no_driver * days
            
            # Create booking
            booking = models.Booking(
                fb_user_id=booking_data.fb_user_id,
                fb_user_name=booking_data.fb_user_name,
                fb_user_phone=booking_data.fb_user_phone,
                vehicle_id=booking_data.vehicle_id,
                driver_id=booking_data.driver_id,
                start_date=booking_data.start_date,
                end_date=booking_data.end_date,
                pickup_location=booking_data.pickup_location,
                dropoff_location=booking_data.dropoff_location,
                total_price=total_price,
                status='pending',
                notes=booking_data.notes
            )
            
            db.add(booking)
            db.commit()
            db.refresh(booking)
            
            logger.info(f"✅ Booking created: {booking.id}")
            return booking
        
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def confirm_booking(booking_id: int, db: Session) -> bool:
        """
        Confirm booking and mark vehicle unavailable
        """
        try:
            booking = db.query(models.Booking).get(booking_id)
            if not booking:
                return False
            
            # Mark unavailable
            from handlers.availability import AvailabilityChecker
            AvailabilityChecker.mark_unavailable(
                booking.vehicle_id,
                booking.start_date,
                booking.end_date,
                booking.id,
                db
            )
            
            # Update status
            booking.status = 'confirmed'
            db.commit()
            
            logger.info(f"✅ Booking confirmed: {booking_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error confirming booking: {e}")
            return False
