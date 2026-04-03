-- ============================================
-- INITIAL SCHEMA FOR VI VU DANANG CHATBOT
-- ============================================

-- 1. FAQ Table (Rule-Based Answers)
CREATE TABLE IF NOT EXISTS faq (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category VARCHAR(50), -- 'gia_ca', 'thu_tuc', 'dich_vu', 'luong_te'
    keywords TEXT, -- "giá|bảng giá|bao nhiêu tiền" để matching
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Vehicles Table (Danh Mục Xe)
CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    seats INT NOT NULL,
    price_per_day_no_driver DECIMAL,
    price_per_day_with_driver DECIMAL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'inactive'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Drivers Table (Quản Lý Tài Xế) - Must be before Bookings
CREATE TABLE IF NOT EXISTS drivers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(15),
    experience_years INT,
    status VARCHAR(20) DEFAULT 'ready', -- 'ready', 'off', 'busy'
    vehicle_type VARCHAR(50), -- '4-seat', '7-seat', '16-seat'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Bookings Table (Lịch Đặt Xe) - Must be before Vehicle Availability
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    fb_user_id VARCHAR(100) NOT NULL, -- Facebook User ID
    fb_user_name VARCHAR(100),
    fb_user_phone VARCHAR(15),
    vehicle_id INT NOT NULL REFERENCES vehicles(id),
    driver_id INT REFERENCES drivers(id) ON DELETE SET NULL, -- NULL = tự lái
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    pickup_location VARCHAR(255),
    dropoff_location VARCHAR(255),
    total_price DECIMAL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'confirmed', 'completed', 'cancelled'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Vehicle Availability Table (Kiểm Tra Xe Trống) - After Bookings
CREATE TABLE IF NOT EXISTS vehicle_availability (
    id SERIAL PRIMARY KEY,
    vehicle_id INT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    busy_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'available', -- 'available', 'booked'
    booking_id INT REFERENCES bookings(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vehicle_id, busy_date)
);

-- 6. Message Logs Table (Lịch Sử Chat)
CREATE TABLE IF NOT EXISTS message_logs (
    id SERIAL PRIMARY KEY,
    fb_user_id VARCHAR(100) NOT NULL,
    role VARCHAR(10) NOT NULL, -- 'user' hoặc 'assistant'
    content TEXT NOT NULL,
    message_type VARCHAR(20), -- 'text', 'quick_reply', 'button', 'image'
    meta_data JSONB, -- Lưu thêm info (button clicked, image URL, etc)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_faq_category ON faq(category);
CREATE INDEX IF NOT EXISTS idx_faq_keywords ON faq(keywords);
CREATE INDEX IF NOT EXISTS idx_vehicle_availability_date ON vehicle_availability(busy_date);
CREATE INDEX IF NOT EXISTS idx_vehicle_availability_status ON vehicle_availability(status);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(fb_user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_message_logs_user ON message_logs(fb_user_id);
CREATE INDEX IF NOT EXISTS idx_message_logs_created ON message_logs(created_at);
