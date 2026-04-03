-- ============================================
-- SEED DATA FOR VI VU DANANG CHATBOT
-- ============================================

-- 1. Insert FAQ Data
INSERT INTO faq (question, answer, category, keywords) VALUES
('Giá thuê xe 4 chỗ?', 'Toyota Vios 4 chỗ: tự lái từ 600k/ngày, có tài xế từ 1.1 triệu/ngày (8 tiếng).', 'gia_ca', 'giá|bao nhiêu|4 chỗ|giá cả'),
('Giá thuê xe 7 chỗ?', 'Mitsubishi Xpander 7 chỗ: tự lái từ 900k/ngày, có tài xế từ 1.4 triệu/ngày (8 tiếng).', 'gia_ca', 'giá|bao nhiêu|7 chỗ|giá cả'),
('Giá thuê xe 16 chỗ?', 'Ford Transit 16 chỗ: Bắt buộc có tài xế, giá từ 2 triệu/ngày.', 'gia_ca', 'giá|bao nhiêu|16 chỗ|giá cả'),
('Thủ tục thuê xe cần gì?', 'Bạn cần: CCCD bản gốc, Bằng lái xe hạng B1/B2 hoặc C, và cọc lại 5 triệu đồng hoặc xe máy chính chủ.', 'thu_tuc', 'thủ tục|cần gì|yêu cầu|giấy tờ'),
('Có giao xe tận nơi không?', 'Có! Vi Vu Đà Nẵng hỗ trợ giao xe tận sân bay hoặc khách sạn miễn phí trong bán kính 5km.', 'dich_vu', 'giao|tận nơi|giao tận|giao xe'),
('Bảng giá có khác ngày hôm nay?', 'Bảng giá của chúng tôi cố định theo ngày. Ngày lễ có thể tăng 10-20%, vui lòng liên hệ để xác nhận giá.', 'gia_ca', 'bảng giá|bao nhiêu|giá cố định'),
('Có xe tự động không?', 'Hiện tại Vi Vu Đà Nẵng chủ yếu cung cấp xe số sàn. Bạn có thể liên hệ để hỏi về xe tự động nếu cần.', 'dich_vu', 'tự động|số sàn|loại xe'),
('Cọc bao nhiêu tiền?', 'Cọc lại 5 triệu đồng hoặc giá trị xe máy chính chủ tương đương.', 'thu_tuc', 'cọc|bao nhiêu|tiền cọc');

-- 2. Insert Vehicles Data
INSERT INTO vehicles (name, seats, price_per_day_no_driver, price_per_day_with_driver, description, status) VALUES
('Toyota Vios 2023', 4, 600000, 1100000, 'Xe 4 chỗ nhỏ gọn, tiết kiệm xăng, phù hợp gia đình nhỏ hoặc cặp đôi.', 'active'),
('Mitsubishi Xpander', 7, 900000, 1400000, 'Xe 7 chỗ rộng rãi, thoải mái hơn Vios, phù hợp gia đình lớn hoặc bạn bè.', 'active'),
('Ford Transit 16-seat', 16, NULL, 2000000, 'Xe 16 chỗ lớn, bắt buộc có tài xế. Phù hợp cho đoàn, một tour hoặc sự kiện.', 'active');

-- 3. Insert Drivers Data
INSERT INTO drivers (full_name, phone, experience_years, status, vehicle_type) VALUES
('Anh Hùng Sông Hàn', '0905123456', 8, 'ready', '4-seat'),
('Chú Bảy Cầu Rồng', '0905789789', 10, 'ready', '7-seat'),
('Bác Mười Cái Năm', '0912345678', 15, 'ready', '16-seat'),
('Anh Tí Bình Minh', '0913456789', 5, 'off', '4-seat');

-- Note: vehicle_availability và bookings sẽ được tạo động qua API
-- message_logs cũng được tạo động khi user chat
