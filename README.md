# Messenger Bot — Người Bạn Tâm Sự Tri Kỷ 🌸

Chatbot Facebook Messenger cá nhân đóng vai **"người bạn thân tri kỷ"**: trò chuyện ấm áp, lắng nghe không phán xét, nhớ lâu dài qua hệ thống trí nhớ 3 tầng, phản chiếu phong cách nói chuyện và bảo vệ an toàn tâm lý.

Toàn bộ công nghệ sử dụng nền tảng **100% MIỄN PHÍ & Open-Source**:
- **LLM**: Groq Cloud API (Free tier: `llama-3.3-70b-versatile` cho hội thoại chính, `llama-3.1-8b-instant` cho tác vụ nền).
- **Database**: PostgreSQL 16 (Supabase). `pgvector` chỉ được giữ để migrations cũ và dữ liệu vector lịch sử vẫn tương thích; runtime không tìm kiếm vector.
- **Framework**: FastAPI (Async Python 3.11) + SQLAlchemy 2.0 + Alembic.

---

## 1. Kiến trúc hệ thống

```
User gửi tin ──► Meta Webhook ──► GET /webhook: verify challenge (không log token)
                                  POST /webhook: HMAC-SHA256 verify (sai -> 403)
                                                 Dedupe theo `mid` (bỏ qua trùng)
                                                 Trả HTTP 200 NGAY (SLA < 3s)
                                                 ▼ (Background Task)
                                           Debounce (~2.5s)
                                                 ▼
                                        User Async Lock (tuần tự)
                                                 ▼
                                        Pipeline Orchestrator
                                ┌────────────────┴────────────────┐
                                │ 1. Kiểm tra lệnh (/help, /nho) │
                                │ 2. Thống kê Style & EMA mirror │
                                │ 3. Kiểm tra An toàn & Khủng hoảng│
                                │ 4. Truy hồi từ khóa PostgreSQL │
                                │ 5. Cắt Window theo Token Budget │
                                │ 6. Dựng Prompt (Persona + Ngữ cảnh)│
                                │ 7. Gọi Groq (Budget & Fallback)│
                                │ 8. Lưu Messages vào Database   │
                                └────────────────┬────────────────┘
                                                 ▼
                                    Gửi tin Messenger Client
                                    (mark_seen ──► typing_on ──► bong bóng ngắt tự nhiên)
                                                 ▼ (Background)
                                    - Tóm tắt cuốn chiếu (>30 tin)
                                    - Trích xuất sự kiện dài hạn (mỗi 6 tin)
```

### Hệ thống Trí nhớ 3 tầng (3-Tier Memory)
1. **Trí nhớ ngắn hạn (Short-term Window)**: Cắt các lượt hội thoại gần nhất nguyên văn dựa trên ngân sách token (~850 token) thay vì số lượng tin cố định. Luôn kết thúc ở tin mới nhất. DB session được giải phóng hoàn toàn trong thời gian gọi LLM.
2. **Tóm tắt cuốn chiếu (Rolling Summary)**: Khi số tin nhắn chưa tóm tắt vượt quá 30, kích hoạt tác vụ nền gọi model `fast` để cô đọng hội thoại thành đoạn tóm tắt dòng chảy (< 300 token) lưu vào bảng `summaries`. Tất cả lời gọi model `fast` đều ghi nhận token usage nguyên tử vào quota ngày.
3. **Ký ức dài hạn**:
   - Chạy nền mỗi 6 tin của user hoặc sau 5 phút không hoạt động (được quản lý bằng asyncio timer task riêng theo từng user, tự động reset mỗi khi user gửi tin mới).
   - Dùng model `fast` ở chế độ JSON mode để trích xuất các sự kiện, sở thích, mục tiêu, cảm xúc sâu sắc về user thành các thao tác `add`, `update`, `delete`.
   - Truy hồi có giới hạn theo user bằng từ khóa đã chuẩn hóa chữ thường, khoảng trắng, dấu câu và bỏ dấu tiếng Việt (`cà phê` khớp `ca phe`). PostgreSQL lọc ứng viên trước khi trả dữ liệu.
   - Điểm xếp hạng: `0.55 × độ phủ từ khóa + 0.25 × exp(-số_ngày/14) + 0.20 × importance/10`. Tối đa 6 mục, 3.000 ký tự; lời chào không có từ khóa chỉ lấy tối đa 3 mục gần đây/quan trọng.
   - Hạn chế: đây là khớp từ khóa, không hiểu đồng nghĩa/ngữ nghĩa như embedding.

---

## 2. Cấu trúc thư mục

```
app/
├── api/                     # webhook, health, dependencies
│   ├── webhook.py           # Webhook Meta (GET challenge, POST event)
│   ├── health.py            # Healthcheck API
│   └── dependencies.py      # Dependency injection qua app.state và Depends
├── chat/                    # Tầng điều phối hội thoại
│   ├── orchestrator.py      # ChatOrchestrator tách các bước TurnContext rõ ràng
│   ├── debounce.py          # MessageDebouncer gộp tin nhắn & dọn dẹp lock/buffer
│   └── commands.py          # Lệnh /help, /nho, /quen
├── persona/                 # Persona & style
│   ├── style.py             # Feature extractor, EMA mirror & render hướng dẫn
│   ├── prompt.py            # Ghép prompt theo thứ tự chuẩn mực
│   └── safety.py            # Bộ lọc khủng hoảng & chống sao chép độc hại
├── memory/                  # Logic AI trí nhớ
│   ├── window.py            # Ước lượng token & cắt sliding window
│   ├── summarizer.py        # Tóm tắt cuốn chiếu nền
│   ├── extractor.py         # Trích xuất sự kiện JSON nền
│   └── retriever.py         # Truy hồi từ khóa, độ mới và độ quan trọng
├── db/                      # Cơ sở dữ liệu & Data Access Layer
│   ├── models.py            # SQLAlchemy models (User, Message, Memory, Summary, LLMUsage)
│   └── store.py             # Repository pattern (flush trong hàm, commit ở điều phối)
├── integrations/            # Tích hợp dịch vụ bên ngoài
│   ├── messenger/           # client (Meta Graph API), dedupe (LRU cache), security (HMAC)
│   └── llm/                 # base (LLMProvider), groq_provider, budget (đếm token atomic)
├── core/                    # Hạ tầng ứng dụng
│   ├── settings.py          # Pydantic-settings, fail-fast startup
│   ├── db.py                # Async engine & sessionmaker (lru_cache)
│   ├── logging.py           # Logging bảo mật (không in token hay nội dung ở INFO)
│   └── tasks.py             # Giữ reference tác vụ nền và log lỗi tự động
├── main.py                  # FastAPI app, lifespan khởi tạo app.state, mount routers
alembic/                     # Alembic database migrations
tests/                       # Toàn bộ test suite (mock mạng, chạy in-memory SQLite)
```

---

## 3. Biến môi trường (.env)

Tạo file `.env` từ `.env.example`:

| Biến | Ý nghĩa | Mặc định / Giá trị mẫu |
| :--- | :--- | :--- |
| `META_VERIFY_TOKEN` | Token bí mật tự đặt để Meta xác thực webhook | `my_verify_secret_token` |
| `META_PAGE_ACCESS_TOKEN` | Access Token của Fanpage từ Meta Developer Console | `EAAG...` |
| `META_APP_SECRET` | App Secret từ trang Cài đặt ứng dụng Meta | `abc123...` |
| `META_API_VERSION` | Phiên bản Graph API của Meta | `v21.0` |
| `GROQ_API_KEY` | Khóa API miễn phí từ console.groq.com | `gsk_...` |
| `GROQ_MODEL_MAIN` | Model chính để trò chuyện với user | `llama-3.3-70b-versatile` |
| `GROQ_MODEL_FAST` | Model phụ chạy nền (tóm tắt & trích xuất) | `llama-3.1-8b-instant` |
| `DAILY_TOKEN_BUDGET_MAIN`| Ngân sách token ngày cho model chính | `100000` |
| `DAILY_TOKEN_BUDGET_FAST`| Ngân sách token ngày cho model phụ | `500000` |
| `DATABASE_URL` | Kết nối PostgreSQL/Supabase | `postgresql+psycopg://postgres:postgres@db:5432/messenger_bot` |
| `LOG_LEVEL` | Cấp độ ghi nhật ký hệ thống | `INFO` |

Múi giờ hiển thị và ranh giới quota được cố định là `Asia/Ho_Chi_Minh`; timestamp trong DB vẫn là UTC có timezone.

---

## 4. Hướng dẫn chạy Local

### Cách 1: Chạy bằng Docker Compose (Khuyên dùng)
```bash
# 1. Clone repository và chuẩn bị file .env
cp .env.example .env
# (Điền các giá trị thực tế vào .env)

# 2. Khởi chạy toàn bộ hệ thống
docker compose up --build -d

# 3. Xem log ứng dụng
docker compose logs -f api
```
- Cơ sở dữ liệu khởi tạo bằng image `pgvector/pgvector:pg16` (cổng 5432 nội bộ, không mở ra host).
- Entrypoint của container `api` sẽ tự động chạy `alembic upgrade head` trước khi khởi động FastAPI server non-root.

### Cách 2: Chạy trực tiếp trên máy host
```bash
# 1. Tạo môi trường ảo Python 3.11
python -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS
# .venv\Scripts\activate   # Trên Windows

# 2. Cài dependency runtime
pip install -r requirements.txt

# 3. Chạy migration
alembic upgrade head

# 4. Khởi động ứng dụng
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

---

## 5. Cấu hình Webhook trên Meta for Developers

1. Mở tunnel công khai trỏ về cổng `8000`:
   ```bash
   ngrok http 8000
   # Hoặc Cloudflare Tunnel:
   cloudflared tunnel --url http://localhost:8000
   ```
2. Truy cập [Meta for Developers](https://developers.facebook.com) > Ứng dụng của bạn > **Messenger** > **Cài đặt**.
3. Tại mục **Webhooks**:
   - Nhấn **Chỉnh sửa URL gọi lại (Callback URL)**:
     - **Callback URL**: `https://<tunnel-domain>/webhook`
     - **Verify Token**: Giá trị của biến `META_VERIFY_TOKEN` trong `.env`.
   - Nhấn **Xác minh và lưu**.
4. Chọn Fanpage của bạn và nhấn **Đăng ký nhận sự kiện (Subscribe)** cho trường `messages` và `messaging_postbacks`.

---

## 6. Lệnh người dùng & Quyền riêng tư

Người dùng có thể gõ trực tiếp các lệnh sau đầu tin nhắn:
- `/help`: Xem giới thiệu về bot và danh sách các lệnh hỗ trợ.
- `/nho`: Xem toàn bộ những gì bot đang ghi nhớ về bạn (tên gọi lấy một lần từ hồ sơ Messenger, cách xưng hô, sự kiện, sở thích...) nhằm minh bạch hóa dữ liệu.
- `/quen`: Xóa vĩnh viễn toàn bộ dữ liệu, gồm tên lấy từ hồ sơ Messenger, ký ức và lịch sử tin nhắn của người dùng khỏi hệ thống theo cơ chế cascade deletion.

---

## 7. Chạy Kiểm thử (Unit & Integration Tests)

Suite regression gọn, độc lập với mạng ngoài và dùng SQLite in-memory. Dependency test không nằm trong production image:
```bash
pip install -r requirements-dev.txt
pytest -q
```

Suite giữ các ranh giới quan trọng: chữ ký webhook, echo/dedup, gửi thất bại hoặc chỉ gửi được một phần, cách ly truy hồi theo user, giới hạn ký ức, `/quen`, và startup không cần Torch/embedding.

Tin nhắn khủng hoảng hoặc chứa từ tục cùng phản hồi ngay sau đó không được đưa vào ký ức dài hạn. Khi tạo tóm tắt cuốn chiếu, mỗi đoạn như vậy được thay bằng một placeholder trung tính; cửa sổ hội thoại trực tiếp vẫn được giữ nguyên để bot có đủ ngữ cảnh phản hồi an toàn.

---

## 8. Giới hạn đã biết (Known Limitations)

1. **Kiến trúc Single Worker (1 Worker)**: Hệ thống được thiết kế chạy với 1 worker process (`--workers 1`). Giả định này giúp quản lý debouncing in-memory, timer trích xuất ký ức sau 5 phút không hoạt động và `asyncio.Lock` tuần tự hóa theo từng người dùng một cách đơn giản. Sau khi khởi động lại, bot dò các tin nhắn chưa qua watermark và khôi phục timer theo nhịp giãn cách để tránh dồn yêu cầu Groq. Nếu muốn mở rộng multi-worker hoặc scale ngang trong tương lai, cần bổ sung một tầng điều phối dùng chung (như Redis Streams hoặc Pub/Sub) cho debounce và distributed lock.
2. **Cửa sổ tin nhắn 24 giờ của Meta (24-Hour Messaging Window)**: Theo chính sách tiêu chuẩn của Facebook Messenger, bot chỉ có thể phản hồi tin nhắn trong vòng 24 giờ kể từ tin nhắn gần nhất của người dùng.
3. **Chế độ phát triển của Meta App (Development Mode)**: Khi ứng dụng Meta đang ở chế độ Development (chưa duyệt Public Live), chỉ các tài khoản Facebook có vai trò trong ứng dụng (Admin, Developer, hoặc Tester) mới có thể nhắn tin và nhận phản hồi từ chatbot.
4. **Truy hồi từ khóa**: không nhận biết từ đồng nghĩa; cần diễn đạt có ít nhất một từ khóa chung để tìm ký ức liên quan.

---

## 9. Các giả định kỹ thuật (Assumptions)

- **Lựa chọn model Groq**: Lựa chọn mặc định là `llama-3.3-70b-versatile` (cho trả lời chính) và `llama-3.1-8b-instant` (cho tóm tắt và trích xuất). Hai model này đều có sẵn và miễn phí trên Groq. Các model có thể tùy chỉnh dễ dàng qua `GROQ_MODEL_MAIN` và `GROQ_MODEL_FAST`.
- **Tương thích dữ liệu cũ**: cột vector và extension không bị xóa. Migration mới chỉ cho phép vector `NULL`; có thể dọn dữ liệu/extension sau bằng một migration riêng khi đã xác nhận không cần rollback.
