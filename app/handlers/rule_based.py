"""
Rule-Based Message Handler
Handles FAQ matching, commands, and entity recognition
"""
import logging
import re
from sqlalchemy.orm import Session
from db import models

logger = logging.getLogger(__name__)

class RuleBasedHandler:
    """
    Handle rule-based matching and commands
    """
    
    @staticmethod
    def extract_keywords(message: str) -> list[str]:
        """Extract keywords from message"""
        # Simple keyword extraction - can be improved
        words = message.lower().split()
        return [w for w in words if len(w) > 3]
    
    @staticmethod
    def match_faq(message: str, db: Session) -> models.FAQ | None:
        """
        Match message against FAQ database
        Returns best matching FAQ or None
        """
        try:
            message_lower = message.lower()
            
            # Query all active FAQs
            faqs = db.query(models.FAQ).all()
            
            best_match = None
            best_score = 0
            
            for faq in faqs:
                if not faq.keywords:
                    continue
                
                keywords = faq.keywords.split("|")
                score = sum(1 for kw in keywords if kw.lower() in message_lower)
                
                if score > best_score:
                    best_score = score
                    best_match = faq
            
            return best_match if best_score > 0 else None
        
        except Exception as e:
            logger.error(f"FAQ matching error: {e}")
            return None
    
    @staticmethod
    def is_command(message: str) -> str | None:
        """
        Check if message is a command (starts with /)
        Returns command name or None
        """
        match = re.match(r'^/(\w+)', message)
        return match.group(1) if match else None
    
    @staticmethod
    def handle_command(command: str, args: str, db: Session) -> str | None:
        """
        Handle specific commands
        """
        commands = {
            "gia": RuleBasedHandler.cmd_price,
            "check": RuleBasedHandler.cmd_check_availability,
            "dat": RuleBasedHandler.cmd_booking,
            "help": RuleBasedHandler.cmd_help,
        }
        
        handler = commands.get(command)
        if handler:
            return handler(args, db)
        return None
    
    @staticmethod
    def cmd_price(args: str, db: Session) -> str:
        """Handle /gia command - show prices"""
        vehicles = db.query(models.Vehicle).filter(models.Vehicle.status == 'active').all()
        
        message = "📋 **BẢNG GIÁ VI VU ĐÀ NẴNG**\n\n"
        for v in vehicles:
            if v.price_per_day_no_driver:
                message += f"🚗 {v.name}:\n"
                message += f"   - Tự lái: {v.price_per_day_no_driver:,}đ/ngày\n"
            if v.price_per_day_with_driver:
                message += f"   - Có tài: {v.price_per_day_with_driver:,}đ/ngày\n"
            message += "\n"
        
        return message
    
    @staticmethod
    def cmd_check_availability(args: str, db: Session) -> str:
        """Handle /check command"""
        return "Vui lòng nhập: /check [ngày] [số chỗ]\nVí dụ: /check 5/4 7"
    
    @staticmethod
    def cmd_booking(args: str, db: Session) -> str:
        """Handle /dat command"""
        return "Bạn muốn đặt xe gì? Hãy nói số chỗ và ngày tháng."
    
    @staticmethod
    def cmd_help(args: str, db: Session) -> str:
        """Handle /help command"""
        return """
📱 **Lệnh khả dụng:**
/gia - Xem bảng giá
/check [ngày] [chỗ] - Kiểm tra xe trống
/dat - Đặt xe
/help - Xem trợ giúp

Hoặc bạn có thể hỏi trực tiếp mà không cần lệnh! 😊
"""
    
    @staticmethod
    def should_route_to_ai(message: str, faq_match: models.FAQ | None) -> bool:
        """
        Decide if message should be routed to AI
        Returns True if no rule-based match found
        """
        return faq_match is None
