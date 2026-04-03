# 🚗 Vi Vu Đà Nẵng — Messenger Chatbot

**Hệ thống chatbot tự động cho thuê xe trên Facebook Messenger**

Sử dụng: FastAPI + PostgreSQL + Gemini AI + Meta Messenger API

**Version:** 1.0 (Phase 1 - Local)  
**Status:** 🟢 Development  
**Last Updated:** April 3, 2026

---

## 📋 Mục tiêu

Xây dựng chatbot Messenger tự động:
- ✅ Trả lời FAQ về giá, thủ tục, loại xe
- ✅ Kiểm tra sẵn có xe trong ngày
- ✅ Xử lý flow đặt xe đa bước
- ✅ AI tư vấn du lịch Đà Nẵng (Gemini)
- ✅ Lưu lịch sử chat + booking vào DB

---

## 🚀 Quick Start

### 1️⃣ Prerequisites
```bash
# Cần có:
- Docker & Docker Compose
- Python 3.11+
- Gemini API key (từ aistudio.google.com)
- Meta Page Access Token (từ Facebook Developers)
```

### 2️⃣ Setup Environment
```bash
# Sao chép template
cp .env.example .env

# Chỉnh sửa .env với credentials của bạn
# - META_VERIFY_TOKEN
# - META_PAGE_ACCESS_TOKEN
# - GEMINI_API_KEY
```

### 3️⃣ Start Containers
```bash
# Build & chạy (PostgreSQL + FastAPI)
docker-compose up -d

# Kiểm tra logs
docker-compose logs -f api

# Kiểm tra databases
docker-compose exec db psql -U postgres -d vi_vu_danang
> \dt  -- List tables
> SELECT * FROM vehicles;  -- Test query
```

### 4️⃣ Test API
```bash
# Health check
curl http://localhost:8000/

# Expected:
# {"status": "ok", "service": "Vi Vu Danang Chatbot", ...}
```

---

## 📁 Project Structure

```
Messenger-bot/
├── 📄 docker-compose.yml      ← Container config (API + PostgreSQL)
├── 📄 Dockerfile              ← Python 3.11 image
├── 📄 requirements.txt         ← Dependencies
├── 📄 .env.example             ← Environment template
│
├── 📁 migrations/
│   ├── 001_initial_schema.sql  ← Create tables (FAQ, Vehicle, Booking, etc.)
│   └── 002_seed_data.sql       ← Sample data
│
├── 📁 app/
│   ├── 📄 main.py             ← FastAPI entry point
│   │
│   ├── 📁 core/
│   │   ├── config.py          ← Load .env variables
│   │   └── database.py        ← SQLAlchemy connection
│   │
│   ├── 📁 db/
│   │   ├── base.py            ← Declarative base
│   │   ├── models.py          ← ORM models (FAQ, Vehicle, Booking, MessageLog)
│   │   ├── schemas.py         ← Pydantic schemas
│   │   ├── crud.py            ← Database CRUD operations
│   │   └── newcrud.py         ← New CRUD (Phase 1)
│   │
│   ├── 📁 handlers/
│   │   ├── webhook.py         ← Meta webhook receiver
│   │   ├── rule_based.py      ← FAQ matcher + commands
│   │   ├── availability.py    ← Vehicle availability checker
│   │   ├── booking.py         ← Multi-step booking flow
│   │   ├── ai.py              ← Gemini AI handler
│   │   └── router.py          ← Message router
│   │
│   ├── 📁 api/ (TODO: Phase 1)
│   │   └── v1/
│   │       ├── routes.py      ← Main API routes
│   │       ├── vehicles.py    ← GET /vehicles, /availability
│   │       ├── bookings.py    ← POST /bookings, GET /bookings
│   │       └── faq.py         ← GET /faq
│   │
│   ├── 📁 utils/
│   │   ├── logger.py          ← Logging setup
│   │   ├── validators.py      ← Input validation
│   │   └── formatters.py      ← Messenger response formatting
│   │
│   └── 📁 ai/
│       ├── gemini.py          ← Gemini API wrapper
│       └── prompts.py         ← System prompts & templates
│
├── 📁 tests/
│   ├── conftest.py            ← Pytest fixtures
│   ├── test_rule_based.py     ← Rule-based handler tests
│   ├── test_ai.py             ← AI handler tests
│   └── test_booking.py        ← Booking flow tests
│
├── 📄 PROPOSAL_VI_VU_DANANG.md  ← Full proposal (read này!)
├── 📄 PHASE1_SETUP.md           ← Setup guide chi tiết
└── 📄 README.md                 ← File này

---

## 💾 Database Schema

6 bảng lưu trữ toàn bộ dữ liệu trên PostgreSQL:

### 1. **FAQ** — Câu hỏi thường gặp
```sql
id | question | answer | category | keywords | created_at
```
- 8 FAQ mẫu về giá, chính sách, dịch vụ
- **keywords**: danh sách từ khóa tìm kiếm (ví dụ: "giá,4 chỗ,tự lái")

### 2. **Vehicle** — Danh sách xe
```sql
id | name | seats | price_per_day_no_driver | price_per_day_with_driver | description | status | created_at
```
- 3 xe mẫu: Vios (4 chỗ), Fortuner (7 chỗ), Kia Morning (4 chỗ)
- Giá riêng: tự lái vs có tài xế
- `status`: 'active' / 'maintenance' / 'inactive'

### 3. **VehicleAvailability** — Calendar xe
```sql
id | vehicle_id (FK) | busy_date | status | booking_id (FK) | created_at
```
- Tracking ngày xe bận/trống
- Unique constraint: (vehicle_id, busy_date)
- `status`: 'available' / 'booked' / 'unavailable'

### 4. **Driver** — Quản lý tài xế
```sql
id | full_name | phone | experience_years | status | vehicle_type | created_at
```
- 4 tài xế mẫu
- `vehicle_type`: khi nào có xe có tài xế
- `status`: 'available' / 'busy' / 'inactive'

### 5. **Booking** — Lịch đặt xe
```sql
id | fb_user_id | fb_user_name | fb_user_phone | vehicle_id (FK) | driver_id (FK) |
start_date | end_date | pickup_location | dropoff_location | total_price | 
status | notes | created_at | updated_at
```
- `status`: 'pending' → 'confirmed' → 'completed' / 'cancelled'
- Indexed: `fb_user_id`, `created_at` (tìm kiếm nhanh)

### 6. **MessageLog** — Lịch sử chat
```sql
id | fb_user_id | role | content | message_type | metadata (JSONB) | created_at
```
- `role`: 'user' / 'assistant'
- `message_type`: 'text' / 'quick_reply' / 'button' / 'image'
- Indexed: `fb_user_id`, `created_at`
- Lưu max 10 tin nhắn gần nhất per user → dùng làm context cho Gemini

---

## 🔄 Message Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Meta Webhook (POST /webhook) ← Facebook Messenger event  │
├─────────────────────────────────────────────────────────────┤
│ Parse: sender_id, recipient_id, message_text, timestamp     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. MessageRouter.route_message() ← Main dispatcher (async)  │
├─────────────────────────────────────────────────────────────┤
│ 3-level fallback logic:                                     │
│   1. Check if /command → RuleBasedHandler.handle_command()  │
│   2. Try FAQ matching → FAQMatcher.match_faq()              │
│   3. Fallback to AI → AIHandler.handle_message()            │
└────────────────────┬────────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌────────────┐
│ Commands   │  │ FAQ Match  │  │ Gemini AI  │
│ /gia       │  │ Keyword    │  │ ask_gemini │
│ /check     │  │ extraction │  │ w/ context │
│ /dat       │  │ & scoring  │  │ + history  │
│ /help      │  │            │  │            │
└────────────┘  └────────────┘  └────────────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Format response ← MessengerFormatter                     │
├─────────────────────────────────────────────────────────────┤
│ Output: text_message() or quick_reply() or button_template()
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Send to Facebook ← webhook.send_message_to_facebook()    │
├─────────────────────────────────────────────────────────────┤
│ POST graph.facebook.com/v18.0/me/messages                   │
│ + Save to message_logs (user + assistant)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Handler Modules

### `handlers/webhook.py`
```python
def parse_webhook_payload(body: dict) -> List[Message]:
    """Extract messages from Meta webhook"""
def send_message_to_facebook(recipient_id, message_data):
    """Send text/quick_reply/button back to user"""
```

### `handlers/rule_based.py`
```python
class RuleBasedHandler:
    def extract_keywords(message: str) -> List[str]:
        """Split text by punctuation, remove stop words"""
    def match_faq(message: str, db) -> Optional[FAQ]:
        """Score all FAQs, return best match (threshold: 0.5)"""
    def is_command(message: str) -> bool:
        """Check if /gia, /check, /dat, /help"""
    def handle_command(command: str, db) -> str:
        """Route commands to handlers"""
```

**Commands:**
- `/gia` → List giá xe tự lái vs có tài
- `/check YYYY-MM-DD` → Check xe trống hôm đó
- `/dat` → Start booking flow
- `/help` → Show all commands

### `handlers/availability.py`
```python
class AvailabilityChecker:
    def check_vehicle_availability(vehicle_id, start_date, end_date, db):
        """Check if vehicle free [start_date, end_date]"""
    def get_available_vehicles(start_date, end_date, min_seats, db):
        """Filter vehicles available + enough seats"""
    def mark_unavailable(vehicle_id, start_date, end_date, booking_id, db):
        """Create busy_date records when booking confirmed"""
```

### `handlers/booking.py`
```python
class BookingHandler:
    def validate_booking(data: BookingCreate, db):
        """Check: date valid, vehicle exists, user phone valid"""
    def create_booking(data: BookingCreate, db) -> Booking:
        """Insert booking with status='pending'"""
    def confirm_booking(booking_id, db):
        """Update status='confirmed', call mark_unavailable()"""
```

### `handlers/ai.py`
```python
class AIHandler:
    async def handle_message(message: str, user_id: str, db):
        """Main AI handler"""
    def get_chat_history(user_id, db) -> List[MessageLog]:
        """Fetch last 10 messages for context"""
    def build_context(db) -> str:
        """Format vehicle pricing + FAQ categories info"""
    def save_message_logs(user_id, role, content, db):
        """Insert user/assistant messages to DB"""
```

### `handlers/router.py`
```python
class MessageRouter:
    async def route_message(message: str, user_id: str, db) -> dict:
        """Main dispatcher with 3-level fallback"""
    def format_message(response: str, type: str) -> dict:
        """Convert to Messenger format (text/quick_reply/button)"""
```

---

## 🤖 AI System (Gemini)

**Setup:**
```python
# app/ai/gemini.py
async def call_gemini_api(user_message, chat_history, context):
    """Send to Gemini v1.5-flash"""
    # System prompt: "Bạn là trợ lý ảo của Vi Vu Đà Nẵng..."
    # Include: user_message + last 10 messages + context (giá xe, FAQ, etc.)
    # Return: AI response
```

**Features:**
- ✅ Chat history context (10 messages)
- ✅ Vehicle pricing info injected
- ✅ System prompt in Vietnamese
- ✅ Fallback message if API fails
- ✅ Async/await (non-blocking)

---

## 📝 Sample Data

**migrations/002_seed_data.sql:**
- 8 FAQs (giá, chính sách, dịch vụ, liên hệ)
- 3 Vehicles (Vios, Fortuner, Morning)
- 4 Drivers (kinh nghiệm 5-10 năm)
- Sample availability records

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Test rule-based matching
pytest tests/test_rule_based.py -v

# Test AI handler
pytest tests/test_ai.py -v

# Test booking flow
pytest tests/test_booking.py -v
```

**Test fixtures (conftest.py):**
- Mock database session
- Mock Gemini API
- Sample FAQ/Vehicle data

---

## 📖 Key Files to Review

1. **[PROPOSAL_VI_VU_DANANG.md](PROPOSAL_VI_VU_DANANG.md)** ← Start here! Full technical proposal
2. **[PHASE1_SETUP.md](PHASE1_SETUP.md)** ← Detailed setup guide
3. **app/main.py** ← FastAPI app, webhook endpoint
4. **app/handlers/router.py** ← Message routing logic
5. **app/db/models.py** ← Database ORM models
6. **migrations/001_initial_schema.sql** ← Database schema

---

## 🔧 Troubleshooting

### PostgreSQL connection error?
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs db

# Restart
docker-compose restart db
```

### API not responding?
```bash
# Check API logs
docker-compose logs api

# Verify migrations ran
docker-compose exec db psql -U postgres -d vi_vu_danang -c "\dt"
```

### Webhook not receiving events?
1. Setup ngrok tunnel: `ngrok http 8000`
2. Get webhook URL: `https://xxxxxx.ngrok.io/webhook`
3. Update Meta webhook endpoint: https://developers.facebook.com/apps/
4. Verify META_VERIFY_TOKEN matches

---

## 🚦 Phase 1 vs Phase 2

| Feature | Phase 1 (Now) | Phase 2 (Later) |
|---------|---|---|
| **Chatbot** | ✅ FAQ + AI | ✅ Advanced NLU |
| **Booking** | ✅ Multi-step flow | ✅ Payment gateway |
| **Storage** | ✅ PostgreSQL local | ✅ Cloud database |
| **Deployment** | Docker local | Cloud (Render/Railway) |
| **Driver GPS** | ❌ | ✅ Real-time tracking |
| **Notifications** | ❌ | ✅ SMS/Email to user |
| **Analytics** | ❌ | ✅ Dashboard |

---

## 📞 Contact & Support

- **Shop:** Vi Vu Đà Nẵng
- **Hotline:** [Số điện thoại shop]
- **Address:** [Địa chỉ shop]
- **Dev:** Update `.env` with your credentials

---

**Last Updated:** April 3, 2026
**Repository:** [GitHub link]
**License:** MIT

| timestamp | user_id | user_message | bot_response | intent | score | fallback |
|-----------|---------|--------------|--------------|--------|-------|----------|
| *(để trống, bot sẽ tự điền)* |

---

## BƯỚC 2 — Tạo Google Service Account

1. Vào [Google Cloud Console](https://console.cloud.google.com)
2. Tạo project mới (hoặc dùng project có sẵn)
3. Vào **APIs & Services** → **Enable APIs** → bật:
   - Google Sheets API
   - Google Drive API
4. Vào **Credentials** → **Create Credentials** → **Service Account**
5. Download file JSON credentials
6. **Share** Google Sheet với email service account (dạng `xxx@xxx.iam.gserviceaccount.com`) — quyền **Editor**

---

## BƯỚC 3 — Chạy local

```bash
# Clone / copy code về
cd vivu-danang-bot

# Tạo virtual env
python -m venv venv
source venv/bin/activate  # Mac/Linux
# hoặc: venv\Scripts\activate  # Windows

# Cài thư viện
pip install -r requirements.txt

# Copy credentials JSON vào thư mục (đặt tên credentials.json)
# hoặc set env var GOOGLE_CREDENTIALS_JSON

# Chạy
uvicorn app.main:app --reload --port 8000
```

Test webhook:
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"message": "giá thuê xe 4 chỗ bao nhiêu", "user_id": "test123", "first_name": "Bạn"}'
```

---

## BƯỚC 4 — Deploy lên Render

1. Push code lên GitHub
2. Vào [render.com](https://render.com) → **New Web Service**
3. Connect GitHub repo
4. Render tự detect `render.yaml`
5. Thêm **Environment Variables**:
   - `GOOGLE_CREDENTIALS_JSON` = paste nội dung file JSON credentials (1 dòng)
   - `SHEET_NAME` = `vivu-danang-bot`
6. Deploy → lấy URL dạng `https://vivu-danang-bot.onrender.com`

---

## BƯỚC 5 — Setup ManyChat

### Tạo Flow "Bot Reply":
1. **Trigger**: "Customer Chat" (mọi tin nhắn)
2. **Action**: External Request (POST)
   - URL: `https://vivu-danang-bot.onrender.com/webhook`
   - Method: POST
   - Body (JSON):
     ```json
     {
       "message": "{{last_input_text}}",
       "user_id": "{{user_id}}",
       "first_name": "{{first name}}"
     }
     ```
3. **Response Mapping**: map `content.messages[0].text` → biến `{{bot_reply}}`
4. **Send Message**: gửi `{{bot_reply}}`

### Tạo Node "Human Handoff":
- Gán conversation cho nhân viên thật
- Gửi thông báo cho admin

---

## Theo dõi hiệu quả

Xem tab `logs` trong Google Sheet để biết:
- Khách hỏi gì nhiều nhất
- Bot fail chỗ nào (`fallback = YES`)
- Score thấp → bổ sung FAQ

---

## Roadmap

- [x] Phase 1: FAQ matching + Booking guide + Fallback
- [ ] Phase 2: OpenAI rewrite answers
- [ ] Phase 3: Check xe trống realtime
- [ ] Phase 4: Tự động lưu booking vào Sheet