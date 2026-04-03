"""
Message Formatters for Messenger API
"""
from typing import Optional

class MessengerFormatter:
    """Format responses for Messenger API"""
    
    @staticmethod
    def text_message(content: str) -> dict:
        """Format as simple text message"""
        return {
            "text": content
        }
    
    @staticmethod
    def quick_reply_message(content: str, options: list[str]) -> dict:
        """
        Format as quick reply message
        
        Args:
            content: Message text
            options: List of reply options (max 13)
        """
        return {
            "text": content,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": opt[:20],  # Max 20 chars per button
                    "payload": opt
                } for opt in options[:13]
            ]
        }
    
    @staticmethod
    def button_message(content: str, buttons: list[dict]) -> dict:
        """
        Format as button message
        
        Args:
            content: Message text
            buttons: List of button dicts
                    {"title": "...", "url": "..."} or
                    {"title": "...", "payload": "..."}
        """
        return {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": content,
                    "buttons": buttons[:3]  # Max 3 buttons
                }
            }
        }
    
    @staticmethod
    def generic_template(elements: list) -> dict:
        """
        Format as generic template (carousel)
        """
        return {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements[:10]  # Max 10 elements
                }
            }
        }
    
    @staticmethod
    def format_vehicle_option(vehicle: dict) -> str:
        """Format vehicle as quick reply option"""
        return f"{vehicle['name']} ({vehicle['seats']}ch)"
    
    @staticmethod
    def format_booking_summary(booking: dict) -> str:
        """Format booking summary for confirmation"""
        summary = f"""
📋 **Thông tin đặt xe:**
• Xe: {booking.get('vehicle_name', 'N/A')}
• Từ: {booking.get('start_date', 'N/A')}
• Đến: {booking.get('end_date', 'N/A')}
• Giá: {booking.get('total_price', 'N/A'):,}đ
• Tài xế: {'Có' if booking.get('driver_id') else 'Tự lái'}

Xác nhận đặt xe trên ứng dụng hoặc liên hệ: 0905 123 456
"""
        return summary.strip()
