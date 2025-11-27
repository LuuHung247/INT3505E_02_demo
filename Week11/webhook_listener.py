from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint để nhận webhook notifications từ Library Management System
    """
    try:
        # Lấy dữ liệu từ request
        data = request.json
        
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        # In ra thông tin đẹp mắt
        print("\n" + "=" * 70)
        print("🔔 WEBHOOK NOTIFICATION RECEIVED")
        print("=" * 70)
        print(f"⏰ Received at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Event Type: {data.get('event', 'N/A')}")
        print(f"🕐 Event Timestamp: {data.get('timestamp', 'N/A')}")
        print("\n📦 Payload Data:")
        print(json.dumps(data.get('data', {}), indent=2, ensure_ascii=False))
        print("=" * 70 + "\n")
        
        # Xử lý theo loại event
        event_type = data.get('event')
        event_data = data.get('data', {})
        
        if event_type == 'book.created':
            print(f"✅ NEW BOOK ADDED:")
            print(f"   📖 Title: {event_data.get('title')}")
            print(f"   ✍️  Author: {event_data.get('author')}")
            print(f"   👤 Created by: {event_data.get('created_by')}")
            print(f"   💬 Message: {event_data.get('message')}")
            
            # Ở đây bạn có thể thêm logic xử lý khác:
            # - Gửi email thông báo
            # - Lưu vào database
            # - Gửi notification đến Slack/Discord
            # - Cập nhật dashboard real-time
            # - Trigger các workflow khác
            
        elif event_type == 'book.created.test':
            print("🧪 TEST WEBHOOK - Everything is working correctly!")
        
        # Trả về response thành công
        return jsonify({
            "status": "success",
            "message": "Webhook received successfully",
            "received_event": event_type,
            "processed_at": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ ERROR processing webhook: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/', methods=['GET', 'POST'])
def home():
    # Nếu là POST request, xử lý như webhook
    if request.method == 'POST':
        return webhook()
    
    # Nếu là GET request, hiển thị trang chủ
    return '''
    <h1>🎣 Webhook Listener</h1>
    <p>Server đang chạy và sẵn sàng nhận webhook notifications!</p>
    <ul>
        <li><strong>Endpoint:</strong> POST / hoặc POST /webhook</li>
        <li><strong>Status:</strong> ✅ Active</li>
    </ul>
    <p>Check console để xem webhook notifications khi chúng đến.</p>
    '''


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "webhook-listener",
        "timestamp": datetime.now().isoformat()
    }), 200


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🎣 WEBHOOK LISTENER STARTING")
    print("=" * 70)
    print("📍 Listening on: http://127.0.0.1:5002")
    print("🔗 Webhook endpoint: http://127.0.0.1:5002/webhook")
    print("\n💡 NEXT STEPS:")
    print("   1. Chạy ngrok: ngrok http http://127.0.0.1:5002")
    print("   2. Copy ngrok URL (https://xxxxx.ngrok-free.app)")
    print("   3. Configure trong Library API: POST /api/v1/webhook/config")
    print("=" * 70 + "\n")
    
    app.run(host='0.0.0.0', port=5002, debug=True)