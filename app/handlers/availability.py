"""
Vehicle Availability Checker
"""
import logging
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from app.db import models

logger = logging.getLogger(__name__)

class AvailabilityChecker:
    """
    Check vehicle availability for date ranges
    """
    
    @staticmethod
    def check_vehicle_availability(
        vehicle_id: int,
        start_date: date,
        end_date: date,
        db: Session
    ) -> dict:
        """
        Check if vehicle is available for date range
        
        Returns:
            {
                'available': bool,
                'booked_dates': [date],
                'vehicle': Vehicle object
            }
        """
        try:
            # Get vehicle
            vehicle = db.query(models.Vehicle).filter(
                models.Vehicle.id == vehicle_id
            ).first()
            
            if not vehicle:
                return {'available': False, 'vehicle': None, 'booked_dates': []}
            
            # Generate all dates in range
            date_range = []
            current = start_date
            while current <= end_date:
                date_range.append(current)
                current += timedelta(days=1)
            
            # Check bookings for those dates
            booked_dates = db.query(models.VehicleAvailability).filter(
                models.VehicleAvailability.vehicle_id == vehicle_id,
                models.VehicleAvailability.busy_date.in_(date_range),
                models.VehicleAvailability.status == 'booked'
            ).all()
            
            booked_date_list = [booking.busy_date for booking in booked_dates]
            available = len(booked_date_list) == 0
            
            return {
                'available': available,
                'vehicle': vehicle,
                'booked_dates': booked_date_list
            }
        
        except Exception as e:
            logger.error(f"Availability check error: {e}")
            return {'available': False, 'vehicle': None, 'booked_dates': []}
    
    @staticmethod
    def get_available_vehicles(
        seats: int,
        start_date: date,
        end_date: date,
        db: Session
    ) -> list[models.Vehicle]:
        """
        Get list of vehicles with required seats available for date range
        """
        try:
            vehicles = db.query(models.Vehicle).filter(
                models.Vehicle.seats >= seats,
                models.Vehicle.status == 'active'
            ).all()
            
            available_vehicles = []
            for vehicle in vehicles:
                result = AvailabilityChecker.check_vehicle_availability(
                    vehicle.id, start_date, end_date, db
                )
                if result['available']:
                    available_vehicles.append(vehicle)
            
            return available_vehicles
        
        except Exception as e:
            logger.error(f"Error getting available vehicles: {e}")
            return []
    
    @staticmethod
    def mark_unavailable(
        vehicle_id: int,
        start_date: date,
        end_date: date,
        booking_id: int,
        db: Session
    ) -> bool:
        """
        Mark vehicle as unavailable for date range
        Used when booking is confirmed
        """
        try:
            current = start_date
            while current <= end_date:
                # Check if already exists
                existing = db.query(models.VehicleAvailability).filter(
                    models.VehicleAvailability.vehicle_id == vehicle_id,
                    models.VehicleAvailability.busy_date == current
                ).first()
                
                if not existing:
                    availability = models.VehicleAvailability(
                        vehicle_id=vehicle_id,
                        busy_date=current,
                        status='booked',
                        booking_id=booking_id
                    )
                    db.add(availability)
                
                current += timedelta(days=1)
            
            db.commit()
            logger.info(f"✅ Marked vehicle {vehicle_id} unavailable for booking {booking_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error marking unavailable: {e}")
            db.rollback()
            return False
