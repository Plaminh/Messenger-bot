"""
Meta Messenger Webhook Handler
"""
import logging
import os
import requests
from app.core.config import META_API_VERSION

logger = logging.getLogger(__name__)

# Use API version from config
FACEBOOK_API_URL = f"https://graph.facebook.com/{META_API_VERSION}/me/messages"
PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "your_page_token")

def send_message_to_facebook(recipient_id: str, message_text: str):
    """
    Gửi tin nhắn trực tiếp về Facebook Messenger
    
    Args:
        recipient_id: Facebook User ID
        message_text: Nội dung tin nhắn (string)
    """
    # Ensure message_text is a string
    if not message_text:
        logger.warning(f"Empty message for {recipient_id}, skipping")
        return False
    
    message_text = str(message_text).strip()
    if not message_text:
        logger.warning(f"Message is only whitespace for {recipient_id}, skipping")
        return False
    
    payload = {
        "recipient": {"id": str(recipient_id)},
        "message": {"text": message_text}
    }
    
    params = {"access_token": PAGE_ACCESS_TOKEN}
    
    try:
        response = requests.post(
            FACEBOOK_API_URL,
            json=payload,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Message sent to {recipient_id}")
            return True
        else:
            logger.error(f"❌ Failed to send message: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"❌ Error sending message to Facebook: {e}", exc_info=True)
        return False
