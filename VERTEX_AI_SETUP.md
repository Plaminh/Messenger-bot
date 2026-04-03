# Setup Google Cloud Vertex AI (Tận dụng $300 Student Credit)

Nếu `gemini-1.5-flash` (AI Studio) vẫn bị 429 quota exceeded, hãy dùng Vertex AI + $300 Student Credit của Google Cloud!

## Tại sao Vertex AI?

| Tiêu chí | AI Studio (Free) | Vertex AI (GCP) |
|---------|-----------------|-----------------|
| Quota | 60 req/min, 1500 req/day | Tùy gói thanh toán |
| Credit | ❌ Không dùng được | ✅ Dùng được $300 |
| Pricing | Miễn phí rồi hết | ~$0.075/1M tokens |
| Setup | Dễ (chỉ cần API key) | Phức tạp hơn (GCP account) |

---

## **Step 1: Vào Google Cloud Console**

```bash
https://console.cloud.google.com/
```

1. **Login** với Google account của bạn (nếu có Student account, dùng cái đó)
2. **Xác nhận project**: Top-left corner có tên project
3. **Enable Billing**: 
   - Sidebar → **Billing** → **Billing Accounts**
   - Nếu có $300 credit, nó sẽ hiện ở đây

---

## **Step 2: Enable Vertex AI APIs**

Vào Search Bar (top) → search result:

### **2.1 Enable Vertex AI API**
```
Search: "Vertex AI API"
Click: Enable
```

### **2.2 Enable Generative Language API**
```
Search: "Generative Language API"
Click: Enable
```

### **2.3 Enable Cloud Resource Manager API**
```
Search: "Cloud Resource Manager API"
Click: Enable
```

---

## **Step 3: Tạo Service Account**

1. **Sidebar** → **IAM & Admin** → **Service Accounts**
2. **Create Service Account**:
   - Service account name: `vi-vu-gemini-bot`
   - Click **Create and Continue**
   - Grant roles → Select **Editor** role
   - Click **Continue** → **Done**

3. **Tạo JSON Key**:
   - Click vào service account vừa tạo
   - Tab **Keys**
   - **Add Key** → **Create new key** → **JSON**
   - Lưu file `service-account-key.json`

---

## **Step 4: Update Docker Environment**

### **4.1 Copy file JSON vào project:**

```bash
# Copy file service-account-key.json vào:
cp ~/Downloads/service-account-key.json ./service-account-key.json
```

### **4.2 Update `.env` file:**

```env
# ─── Gemini AI Type ──────────────────────────────
GEMINI_API_TYPE=vertex_ai
GEMINI_MODEL=gemini-1.5-flash

# ─── Google Cloud ────────────────────────────────
GCP_PROJECT_ID=your-gcp-project-id-here
GCP_LOCATION=us-central1

# ─── Gemini API Key (path to JSON) ──────────────
GEMINI_API_KEY=./service-account-key.json
```

### **4.3 Update docker-compose.yml:**

```yaml
services:
  api:
    # ... existing config ...
    volumes:
      - ./service-account-key.json:/app/service-account-key.json:ro
    environment:
      - GEMINI_API_TYPE=${GEMINI_API_TYPE}
      - GCP_PROJECT_ID=${GCP_PROJECT_ID}
      - GCP_LOCATION=${GCP_LOCATION}
      # ... other env vars ...
```

---

## **Step 5: Switch Code to Vertex AI**

### **5.1 Update imports in `app/handlers/ai.py`:**

**Change from:**
```python
from app.ai.gemini import call_gemini_api
```

**To:**
```python
from app.ai.gemini_vertex import call_gemini_api
```

OR update `app/ai/gemini.py` to import từ `gemini_vertex.py`:

```python
# In app/ai/gemini.py
from app.core.config import GEMINI_API_TYPE

if GEMINI_API_TYPE == "vertex_ai":
    from app.ai.gemini_vertex import call_gemini_api
else:
    from app.ai.gemini import call_gemini_api  # AI Studio
```

### **5.2 Install Google Cloud SDK:**

```bash
docker compose exec api pip install google-cloud-aiplatform
```

---

## **Step 6: Restart & Test**

```bash
# Restart API
docker compose restart api

# Check logs
docker compose logs api -f

# Test by sending message to bot
# Should see: "✅ Vertex AI response generated"
```

---

## **Troubleshooting**

### ❌ "vertexai SDK not installed"
```bash
docker compose exec api pip install google-cloud-aiplatform
docker compose restart api
```

### ❌ "Credentials not found"
- Check `service-account-key.json` exists in project root
- Check `GCP_PROJECT_ID` matches project ID từ JSON file
- Mở JSON file, field `project_id` phải match

### ❌ "Permission denied"
- Go to Cloud Console → **IAM & Admin** → **IAM**
- Find service account → Edit → Ensure **Editor** role is granted

### ✅ Success!
- Log sẽ show: `✅ Vertex AI response generated`
- Bot sẽ reply Messenger messages bình thường
- Credit sẽ tự động trừ khi dùng API

---

## **So Sánh Chi Phí**

Với $300 credit và mức yêu cầu Phase 1:

```
Giá Vertex AI:
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens

Ví dụ:
- 100 cuộc chat/ngày × 200 tokens/chat = 20K tokens/ngày
- 20K × 0.075 / 1M = $0.0015/ngày
- → $300 = ~200,000 ngày!

Kết luận: $300 credits sẽ đủ dùng RẤT LẦU cho Phase 1 🎉
```

---

## **Nếu vẫn cần help, hãy nói:**
- Đã lấy được GCP Project ID chưa?
- Đã tạo Service Account JSON chưa?
- Có error gì không?
