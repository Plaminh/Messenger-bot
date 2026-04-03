"""
Input Validators
"""
import re
from datetime import date
from typing import Tuple

class Validators:
    """Input validation utilities"""
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate Vietnam phone number"""
        if not phone:
            return False
        # Simple validation: must be 10-11 digits starting with 0
        phone = phone.strip()
        return bool(re.match(r'^0\d{9,10}$', phone))
    
    @staticmethod
    def validate_date_range(start_date: date, end_date: date) -> Tuple[bool, str]:
        """Validate date range"""
        if start_date > end_date:
            return False, "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc."
        
        if start_date < date.today():
            return False, "Ngày bắt đầu phải từ hôm nay trở đi."
        
        days = (end_date - start_date).days + 1
        if days > 30:
            return False, "Không thể đặt quá 30 ngày. Vui lòng liên hệ shop."
        
        return True, "OK"
    
    @staticmethod
    def validate_seats(seats: int) -> bool:
        """Validate number of seats"""
        return seats in [4, 7, 16]
    
    @staticmethod
    def validate_message(message: str) -> bool:
        """Validate user message"""
        if not message:
            return False
        
        message = message.strip()
        
        # Too short
        if len(message) < 2:
            return False
        
        # Too long (>1000 chars)
        if len(message) > 1000:
            return False
        
        return True
    
    @staticmethod
    def parse_date(date_str: str) -> date | None:
        """
        Parse Vietnamese date format
        Supports: "5/4", "5/4/2026", "05/04/2026"
        """
        try:
            parts = date_str.strip().split('/')
            
            if len(parts) == 2:
                day, month = int(parts[0]), int(parts[1])
                year = date.today().year
            elif len(parts) == 3:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                return None
            
            return date(year, month, day)
        
        except (ValueError, IndexError):
            return None
