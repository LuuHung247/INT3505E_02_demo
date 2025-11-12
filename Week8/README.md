Chạy Unit Tests

# Chạy tất cả unit tests

pytest test_api.py -v

# Chạy với coverage report

pytest test_api.py -v --cov=app --cov-report=html

# Chạy test cụ thể

pytest test_api.py::TestAuthentication::test_login_success -v

# Xem coverage report

open htmlcov/index.html

Chạy Newman Tests

# Import collection vào Postman để test thủ công

# hoặc chạy tự động với Newman:

newman run Book_API_Tests.postman_collection.json -e Book_API_Environment.json \
 --reporters cli,htmlextra \
 --reporter-htmlextra-export ./test-reports/newman-report.html

# Chạy Locust với Web UI

locust -f locustfile.py --host=http://localhost:5001

# Sau đó mở browser: http://localhost:8089

# Nhập: 50 users, spawn rate 5

# Hoặc chạy headless mode

locust -f locustfile.py \
 --host=http://localhost:5001 \
 --users 100 \
 --spawn-rate 10 \
 --run-time 60s \
 --headless \
 --html test-reports/locust-report.html
