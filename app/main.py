from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
import logging
import os
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Ensure app directory is in Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Internal imports
from app.core.config import HOST, PORT, DEBUG, META_VERIFY_TOKEN, DATABASE_URL, APP_NAME, APP_VERSION
from app.core.database import get_db, init_db
from app.core.migrations import run_migrations
from app.handlers.webhook import send_message_to_facebook
from app.handlers.router import MessageRouter
from app.api.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=APP_NAME,
    description="Messenger chatbot cho thuê xe with PostgreSQL + Gemini AI (Phase 1)",
    version=APP_VERSION
)

# ─── Health Check ───────────────────────────────────────────────
@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
        "database": "postgresql"
    }

# ─── Startup Event ──────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    """Initialize database and run migrations on startup"""
    logger.info(f"🚀 Starting {APP_NAME} v{APP_VERSION}...")
    try:
        # Run auto-migrations
        logger.info("🔄 Running auto-migrations...")
        run_migrations(DATABASE_URL)
        
        # Initialize database (create tables if not exist)
        init_db()
        logger.info("✅ Database ready")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}", exc_info=True)
        # Don't crash - just warn

# ─── Include API Routes ──────────────────────────────────────────
app.include_router(api_router)

# ─── Meta Messenger Webhook ─────────────────────────────────────

@app.get("/webhook")
def verify_webhook(request: Request):
    """Xác thực webhook từ Meta"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    logger.info(f"Webhook verify request: mode={mode}, token={token}, challenge={challenge}")
    
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        logger.info("✅ Webhook verified!")
        return PlainTextResponse(challenge)
    else:
        logger.warning(f"❌ Webhook verification failed. Expected: {META_VERIFY_TOKEN}, Got: {token}")
        return JSONResponse({"error": "Forbidden"}, status_code=403)

@app.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Nhận & xử lý tin nhắn từ Meta Messenger"""
    try:
        body = await request.json()
        logger.info(f"[META] Webhook received: {body.get('object')}")
        
        if body.get("object") != "page":
            return JSONResponse({"status": "ok"})
        
        # ─── Process messaging events ──────────────────────────
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                
                # Skip if no message
                if "message" not in messaging_event:
                    continue
                
                sender_id = messaging_event["sender"]["id"]
                message_obj = messaging_event["message"]
                
                # Skip echo (bot reply)
                if message_obj.get("is_echo"):
                    continue
                
                # Only process text messages
                user_message = message_obj.get("text", "").strip()
                if not user_message:
                    continue
                
                logger.info(f"[{sender_id}] Message: {user_message}")
                
                # ─── Route message using new handler ───────────
                try:
                    response = await MessageRouter.route_message(
                        message=user_message,
                        user_id=sender_id,
                        db=db
                    )
                    
                    # ─── Send response back to Messenger ───────
                    # Handle both string and dict responses
                    if response:
                        if isinstance(response, dict):
                            message_text = response.get("text", "")
                        else:
                            message_text = str(response)
                        
                        if message_text:
                            send_message_to_facebook(sender_id, message_text)
                            logger.info(f"✅ Response sent to {sender_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Error routing message: {e}", exc_info=True)
                    # Send fallback message
                    fallback = {"text": "Xin lỗi, gặp lỗi. Vui lòng thử lại sau!"}
                    send_message_to_facebook(sender_id, fallback)
        
        return JSONResponse({"status": "ok"})
    
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}", exc_info=True)
        return JSONResponse({"status": "error"}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG
    )
