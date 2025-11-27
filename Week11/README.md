# 🔔 Hướng dẫn Setup Webhook cho Library Management API

## 📋 Tổng quan

Hệ thống webhook cho phép bạn nhận thông báo real-time khi có sách mới được thêm vào thư viện.

## 🚀 Cài đặt từng bước

### Bước 1: Chuẩn bị môi trường

```bash
# Cài đặt dependencies
pip install flask flask-cors pyjwt pymongo python-dotenv flask-limiter flask-swagger-ui requests
```

### Bước 2: Tạo file .env

```env
SECRET_KEY=your-secret-key-here
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=library_db
WEBHOOK_URL=
```

### Bước 3: Chạy Webhook Listener

```bash
# Terminal 1: Chạy webhook listener
python webhook_listener.py
```

Bạn sẽ thấy:

```
====================================================================
🎣 WEBHOOK LISTENER STARTING
====================================================================
📍 Listening on: http://127.0.0.1:5000
🔗 Webhook endpoint: http://127.0.0.1:5000/webhook
```

### Bước 4: Setup Ngrok

```bash
# Terminal 2: Chạy ngrok để expose webhook listener
ngrok http http://127.0.0.1:5000
```

**Output ngrok:**

```
Forwarding    https://abc123.ngrok-free.app -> http://127.0.0.1:5000
```

**📝 Lưu ý:** Copy URL `https://abc123.ngrok-free.app` (URL của bạn sẽ khác)

### Bước 5: Chạy Main API

```bash
# Terminal 3: Chạy Library Management API
python app.py
```

## 🧪 Test Webhook

### 1. Login và lấy token

```bash
curl -X POST http://localhost:5001/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "123456"
  }'
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

### 2. Cấu hình Webhook URL

```bash
curl -X POST http://localhost:5001/api/v1/webhook/config \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "webhook_url": "https://abc123.ngrok-free.app/webhook"
  }'
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "webhook_url": "https://abc123.ngrok-free.app/webhook",
    "message": "Webhook URL configured successfully"
  }
}
```

### 3. Test Webhook

```bash
curl -X POST http://localhost:5001/api/v1/webhook/test \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Kết quả trong Terminal 1 (webhook_listener.py):**

```
======================================================================
🔔 WEBHOOK NOTIFICATION RECEIVED
======================================================================
⏰ Received at: 2025-11-27 10:30:45
📋 Event Type: book.created.test
🕐 Event Timestamp: 2025-11-27T03:30:45.123456Z

📦 Payload Data:
{
  "book_id": "test_20251127103045",
  "title": "Test Book - Clean Code",
  "author": "Robert C. Martin",
  "available": true,
  "created_by": "admin",
  "message": "🧪 Đây là TEST webhook notification"
}
======================================================================

🧪 TEST WEBHOOK - Everything is working correctly!
```

### 4. Thêm sách mới (thật)

```bash
curl -X POST http://localhost:5001/api/v1/books \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "title": "Clean Code",
    "author": "Robert C. Martin"
  }'
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "_id": "674696b1c8f9a8e1234567",
    "title": "Clean Code",
    "author": "Robert C. Martin",
    "available": true
  },
  "message": "Book created and webhook notification sent"
}
```

**Webhook notification trong Terminal 1:**

```
======================================================================
🔔 WEBHOOK NOTIFICATION RECEIVED
======================================================================
⏰ Received at: 2025-11-27 10:35:22
📋 Event Type: book.created
🕐 Event Timestamp: 2025-11-27T03:35:22.789012Z

📦 Payload Data:
{
  "book_id": "674696b1c8f9a8e1234567",
  "title": "Clean Code",
  "author": "Robert C. Martin",
  "available": true,
  "created_by": "admin",
  "created_at": "2025-11-27T03:35:22.789012Z",
  "message": "📚 Sách mới 'Clean Code' của tác giả Robert C. Martin đã được thêm vào thư viện!"
}
======================================================================

✅ NEW BOOK ADDED:
   📖 Title: Clean Code
   ✍️  Author: Robert C. Martin
   👤 Created by: admin
   💬 Message: 📚 Sách mới 'Clean Code' của tác giả Robert C. Martin đã được thêm vào thư viện!
```

## 📊 Cấu trúc Webhook Payload

```json
{
  "event": "book.created",
  "timestamp": "2025-11-27T03:30:45.123456Z",
  "data": {
    "book_id": "674696b1c8f9a8e1234567",
    "title": "Clean Code",
    "author": "Robert C. Martin",
    "available": true,
    "created_by": "admin",
    "created_at": "2025-11-27T03:30:45.123456Z",
    "message": "📚 Sách mới được thêm vào thư viện!"
  }
}
```

## 🔧 API Endpoints

### Webhook Management

| Method | Endpoint                 | Description          | Auth Required   |
| ------ | ------------------------ | -------------------- | --------------- |
| GET    | `/api/v1/webhook/config` | Xem cấu hình webhook | ✅              |
| POST   | `/api/v1/webhook/config` | Cấu hình webhook URL | ✅ (Admin only) |
| POST   | `/api/v1/webhook/test`   | Test gửi webhook     | ✅              |

### Example: Xem cấu hình

```bash
curl -X GET http://localhost:5001/api/v1/webhook/config \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## 🎯 Use Cases

### 1. Gửi Email Notification

```python
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get('event') == 'book.created':
        book_data = data.get('data', {})
        send_email(
            to="librarian@example.com",
            subject=f"Sách mới: {book_data.get('title')}",
            body=book_data.get('message')
        )
    return jsonify({"status": "success"}), 200
```

### 2. Gửi Slack Notification

```python
import requests

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get('event') == 'book.created':
        book_data = data.get('data', {})

        # Gửi đến Slack
        slack_webhook = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
        requests.post(slack_webhook, json={
            "text": f"📚 Sách mới: *{book_data.get('title')}* - {book_data.get('author')}"
        })

    return jsonify({"status": "success"}), 200
```

### 3. Lưu vào Database

```python
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get('event') == 'book.created':
        # Lưu vào logs database
        logs_collection.insert_one({
            "event": data.get('event'),
            "timestamp": data.get('timestamp'),
            "data": data.get('data'),
            "processed_at": datetime.now()
        })

    return jsonify({"status": "success"}), 200
```

## 🐛 Troubleshooting

### Webhook không nhận được thông báo

1. **Kiểm tra ngrok đang chạy:**

   ```bash
   # Xem status trong ngrok terminal
   # Phải thấy "online" status
   ```

2. **Kiểm tra webhook URL đã cấu hình:**

   ```bash
   curl -X GET http://localhost:5001/api/v1/webhook/config \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

3. **Xem logs trong Terminal 3 (main API):**

   ```
   📤 Đang gửi webhook đến: https://abc123.ngrok-free.app/webhook
   ✅ Webhook sent successfully - Status: 200
   ```

4. **Kiểm tra firewall/antivirus:** Có thể block ngrok connections

### Ngrok session expired

```bash
# Chạy lại ngrok
ngrok http http://127.0.0.1:5000

# Update webhook URL với URL mới
curl -X POST http://localhost:5001/api/v1/webhook/config \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"webhook_url": "https://NEW_URL.ngrok-free.app/webhook"}'
```
