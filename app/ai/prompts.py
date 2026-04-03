"""
AI Prompts and Templates for Vi Vu Danang
"""

# System prompts
SYSTEM_PROMPT_VI_VU = """Bạn là trợ lý ảo của Vi Vu Đà Nẵng - công ty cho thuê xe du lịch tại Đà Nẵng.

Trách nhiệm:
1. Tư vấn lịch trình du lịch Đà Nẵng
2. Giới thiệu các loại xe và giá cả
3. Hỗ trợ quá trình đặt xe
4. Trả lời các câu hỏi về thủ tục, chính sách
5. Gợi ý loại xe phù hợp dựa trên nhu cầu

Tông lửa: Thân thiện, tích cực, hỗ trợ, chuyên nghiệp.

Lưu ý:
- Trả lời ngắn gọn, rõ ràng (dưới 500 ký tự)
- Sử dụng emoji thích hợp
- Không commit giá cả quá chính xác nếu không chắc
- Khuyến khích khách sử dụng hệ thống đặt xe"""

# Vehicle info template
VEHICLE_INFO_TEMPLATE = """**Danh sách xe Vi Vu Đà Nẵng:**

🚗 **4 chỗ (Toyota Vios):**
   - Giá tự lái: 600,000đ/ngày
   - Giá có tài: 1,100,000đ/ngày
   - Phù hợp: Cặp đôi, gia đình nhỏ

🚐 **7 chỗ (Mitsubishi Xpander):**
   - Giá tự lái: 900,000đ/ngày
   - Giá có tài: 1,400,000đ/ngày
   - Phù hợp: Gia đình lớn, bạn bè

🚌 **16 chỗ (Ford Transit):**
   - Giá: 2,000,000đ/ngày (bắt buộc có tài)
   - Phù hợp: Đoàn, tour, sự kiện"""

# FAQ categories
FAQ_CATEGORIES = {
    'gia_ca': 'Giá cả',
    'thu_tuc': 'Thủ tục', 
    'dich_vu': 'Dịch vụ',
    'luong_te': 'Lương tế/Khác',
}

# Common intents
INTENTS = {
    'greeting': ['xin chào', 'chào', 'hello', 'hi'],
    'price_inquiry': ['giá', 'bao nhiêu', 'chi phí', 'bảng giá'],
    'booking': ['đặt', 'book', 'thuê', 'muốn'],
    'availability': ['còn', 'trống', 'available'],
    'location': ['đà nẵng', 'đn', 'sân bay', 'khách sạn'],
    'procedure': ['thủ tục', 'cần gì', 'yêu cầu', 'giấy tờ'],
}
