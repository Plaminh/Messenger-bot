# Vi vu Đà Nẵng — Messenger Bot

Bot tự động trả lời Messenger cho dịch vụ cho thuê xe, build với FastAPI + Google Sheet + ManyChat.

---

## Cấu trúc project

```
vivu-danang-bot/
├── app/
│   ├── main.py        ← FastAPI app, webhook endpoint
│   ├── handlers.py    ← Xử lý logic tin nhắn
│   ├── matcher.py     ← Fuzzy matching + intent detection
│   ├── sheet.py       ← Đọc data từ Google Sheet
│   └── logger.py      ← Lưu log vào Google Sheet
├── requirements.txt
├── render.yaml        ← Deploy lên Render
└── .env.example       ← Mẫu biến môi trường
```

---

## BƯỚC 1 — Setup Google Sheet

### Tạo Spreadsheet mới tên: `vivu-danang-bot`

### Tạo 4 tab (worksheet):

---

### Tab 1: `faq`

| id | question | answer | tags | category |
|----|----------|--------|------|----------|
| 1 | Shop có giao xe tận nơi không? | Dạ shop có dịch vụ giao xe tận nơi trong nội thành Đà Nẵng ạ, phí phụ thu theo khoảng cách 🚗 | giao xe,tận nơi,deliver | service |
| 2 | Thuê xe cần giấy tờ gì? | Dạ bạn cần CMND/CCCD và bằng lái xe còn hạn ạ. Nếu thuê xe có tài thì chỉ cần CMND thôi nhé! | giấy tờ,cmnd,bằng lái,hồ sơ | policy |
| 3 | Đặt cọc bao nhiêu? | Dạ shop thu cọc 30% giá trị thuê khi đặt lịch ạ, thanh toán phần còn lại khi nhận xe 💳 | đặt cọc,cọc,deposit | payment |
| 4 | Có hủy được không? | Dạ bạn có thể hủy trước 24h và được hoàn cọc 100% ạ. Hủy trong vòng 24h sẽ mất cọc nhé! | hủy,hoàn tiền,cancel,refund | policy |
| 5 | Giá thuê xe 4 chỗ bao nhiêu? | Dạ xe 4 chỗ tự lái từ 700.000đ/ngày, có tài từ 1.200.000đ/ngày ạ 🚗 | giá,4 chỗ,xe 4,tự lái | price |
| 6 | Giá thuê xe 7 chỗ? | Dạ xe 7 chỗ tự lái từ 900.000đ/ngày, có tài từ 1.500.000đ/ngày ạ | giá,7 chỗ,xe 7 | price |
| 7 | Shop ở đâu? | Dạ Vi vu Đà Nẵng ở [địa chỉ shop] ạ. Bạn có thể Google Maps "[tên shop]" để tìm đường nhé 📍 | địa chỉ,ở đâu,location | contact |
| 8 | Hotline shop? | Dạ hotline Vi vu Đà Nẵng là [số điện thoại] ạ. Hoặc nhắn Zalo cùng số này nhé! 📞 | hotline,sdt,số điện thoại,zalo | contact |
| 9 | Có thuê theo giờ không? | Dạ shop chỉ cho thuê theo ngày ạ (tính từ 8h sáng). Nếu bạn cần thuê nửa ngày thì nhắn shop tư vấn thêm nhé! | theo giờ,nửa ngày,hourly | service |
| 10 | Xe có bảo hiểm không? | Dạ tất cả xe của shop đều có bảo hiểm dân sự đầy đủ ạ. Bạn yên tâm nhé! 🛡️ | bảo hiểm,insurance | policy |

---

### Tab 2: `vehicles`

| id | name | seats | price_per_day | has_driver | description | available |
|----|------|-------|---------------|------------|-------------|-----------|
| 1 | Toyota Vios | 4 | 700.000đ | FALSE | Xe phổ thông, tiết kiệm xăng | TRUE |
| 2 | Toyota Fortuner | 7 | 950.000đ | FALSE | SUV rộng rãi, phù hợp đi tỉnh | TRUE |
| 3 | Kia Morning | 4 | 650.000đ | FALSE | Xe nhỏ gọn, dễ đậu | TRUE |
| 4 | Toyota Innova | 7 | 900.000đ | TRUE | Có tài xế kinh nghiệm | TRUE |
| 5 | Hyundai Accent | 4 | 720.000đ | FALSE | Mới, đẹp, tiện nghi | TRUE |

---

### Tab 3: `bookings`

| id | user_id | user_name | phone | pickup_date | return_date | vehicle | driver_needed | status | created_at |
|----|---------|-----------|-------|-------------|-------------|---------|---------------|--------|------------|
| *(để trống, bot sẽ tự điền)* |

---

### Tab 4: `logs`

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

## 📱 BƯỚC 5 — Setup ManyChat

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