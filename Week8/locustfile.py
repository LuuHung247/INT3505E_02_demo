from locust import HttpUser, task, between, events
import json
import random
import jwt
import datetime
from datetime import timedelta

# Global variable để lưu token
auth_token = None

class BookAPIUser(HttpUser):
    """
    Simulate user behavior cho Book Management API
    Performance testing với các scenarios khác nhau
    """
    
    # Thời gian chờ giữa các requests (giây)
    wait_time = between(1, 3)
    
    # API endpoint prefix
    api_prefix = "/api/v1"
    
    def on_start(self):
        """
        Được gọi khi user bắt đầu - Login để lấy token
        """
        self.login()
    
    def login(self):
        """Đăng nhập và lưu token"""
        global auth_token
        
        response = self.client.post(
            f"{self.api_prefix}/login",
            json={"username": "admin", "password": "123456"},
            name="Login"
        )
        
        if response.status_code == 200:
            data = response.json()
            auth_token = data['data']['token']
            self.token = auth_token
        else:
            print(f"Login failed: {response.status_code}")
    
    def get_auth_headers(self):
        """Tạo headers với token"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    @task(5)
    def get_all_books(self):
        """
        Task: Lấy danh sách tất cả sách
        Weight: 5 (chạy nhiều nhất - 50% requests)
        """
        with self.client.get(
            f"{self.api_prefix}/books",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="GET /books"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'books' in data['data']:
                    response.success()
                else:
                    response.failure("Invalid response structure")
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(2)
    def search_books_by_title(self):
        """
        Task: Tìm kiếm sách theo title
        Weight: 2 (20% requests)
        """
        search_terms = ['Clean', 'Design', 'Python', 'Java', 'Test']
        term = random.choice(search_terms)
        
        with self.client.get(
            f"{self.api_prefix}/books?title={term}",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="GET /books?title=..."
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Search failed: {response.status_code}")
    
    @task(2)
    def filter_available_books(self):
        """
        Task: Lọc sách còn/hết
        Weight: 2 (20% requests)
        """
        available = random.choice(['true', 'false'])
        
        with self.client.get(
            f"{self.api_prefix}/books?available={available}",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="GET /books?available=..."
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Filter failed: {response.status_code}")
    
    @task(1)
    def create_and_delete_book(self):
        """
        Task: Tạo sách mới và xóa luôn
        Weight: 1 (10% requests)
        Scenario: Test CRUD workflow
        """
        # 1. Create book
        new_book = {
            "title": f"Load Test Book {random.randint(1000, 9999)}",
            "author": f"Author {random.randint(1, 100)}"
        }
        
        with self.client.post(
            f"{self.api_prefix}/books",
            json=new_book,
            headers=self.get_auth_headers(),
            catch_response=True,
            name="POST /books (create)"
        ) as response:
            if response.status_code == 201:
                data = response.json()
                book_id = data['data']['_id']
                response.success()
                
                # 2. Delete book
                with self.client.delete(
                    f"{self.api_prefix}/books/{book_id}",
                    headers=self.get_auth_headers(),
                    catch_response=True,
                    name="DELETE /books/:id"
                ) as del_response:
                    if del_response.status_code == 200:
                        del_response.success()
                    else:
                        del_response.failure(f"Delete failed: {del_response.status_code}")
            else:
                response.failure(f"Create failed: {response.status_code}")


class ReadHeavyUser(HttpUser):
    """
    Scenario: User chỉ đọc dữ liệu (90% GET requests)
    Mô phỏng traffic thực tế - đa số user chỉ xem
    """
    wait_time = between(0.5, 2)
    api_prefix = "/api/v1"
    
    def on_start(self):
        self.login()
    
    def login(self):
        global auth_token
        response = self.client.post(
            f"{self.api_prefix}/login",
            json={"username": "admin", "password": "123456"}
        )
        if response.status_code == 200:
            self.token = response.json()['data']['token']
    
    def get_auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    @task(9)
    def browse_books(self):
        """Duyệt sách"""
        self.client.get(
            f"{self.api_prefix}/books",
            headers=self.get_auth_headers(),
            name="Browse Books"
        )
    
    @task(1)
    def search_books(self):
        """Tìm kiếm"""
        term = random.choice(['Python', 'Java', 'Clean', 'Design'])
        self.client.get(
            f"{self.api_prefix}/books?title={term}",
            headers=self.get_auth_headers(),
            name="Search Books"
        )


class WriteHeavyUser(HttpUser):
    """
    Scenario: User thao tác nhiều (tạo, sửa, xóa)
    Test database write performance
    """
    wait_time = between(2, 5)
    api_prefix = "/api/v1"
    
    def on_start(self):
        self.login()
    
    def login(self):
        response = self.client.post(
            f"{self.api_prefix}/login",
            json={"username": "admin", "password": "123456"}
        )
        if response.status_code == 200:
            self.token = response.json()['data']['token']
    
    def get_auth_headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    @task(4)
    def create_book(self):
        """Tạo sách mới"""
        book = {
            "title": f"Book {random.randint(1000, 9999)}",
            "author": f"Author {random.randint(1, 100)}"
        }
        self.client.post(
            f"{self.api_prefix}/books",
            json=book,
            headers=self.get_auth_headers(),
            name="Create Book"
        )
    
    @task(3)
    def update_book(self):
        """Cập nhật sách ngẫu nhiên"""
        # Get a book first
        response = self.client.get(
            f"{self.api_prefix}/books",
            headers=self.get_auth_headers()
        )
        if response.status_code == 200:
            books = response.json()['data']['books']
            if books:
                book_id = random.choice(books)['_id']
                update_data = {
                    "available": random.choice([True, False])
                }
                self.client.put(
                    f"{self.api_prefix}/books/{book_id}",
                    json=update_data,
                    headers=self.get_auth_headers(),
                    name="Update Book"
                )
    
    @task(3)
    def delete_book(self):
        """Xóa sách ngẫu nhiên"""
        response = self.client.get(
            f"{self.api_prefix}/books",
            headers=self.get_auth_headers()
        )
        if response.status_code == 200:
            books = response.json()['data']['books']
            if books:
                book_id = random.choice(books)['_id']
                self.client.delete(
                    f"{self.api_prefix}/books/{book_id}",
                    headers=self.get_auth_headers(),
                    name="Delete Book"
                )


# ==================== Event Listeners ====================
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Chạy khi test bắt đầu"""
    print("\n" + "="*70)
    print("🚀 STARTING PERFORMANCE TEST")
    print("="*70)
    print(f"Target Host: {environment.host}")
    print(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("="*70 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Chạy khi test kết thúc - Tạo report summary"""
    print("\n" + "="*70)
    print("📊 PERFORMANCE TEST SUMMARY")
    print("="*70)
    
    stats = environment.stats
    
    print("\n📈 Request Statistics:")
    print(f"   Total Requests: {stats.total.num_requests}")
    print(f"   Failed Requests: {stats.total.num_failures}")
    print(f"   Failure Rate: {(stats.total.fail_ratio * 100):.2f}%")
    
    print("\n⏱️  Response Time:")
    print(f"   Average: {stats.total.avg_response_time:.2f}ms")
    print(f"   Median: {stats.total.median_response_time:.2f}ms")
    print(f"   95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"   99th Percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    print(f"   Min: {stats.total.min_response_time:.2f}ms")
    print(f"   Max: {stats.total.max_response_time:.2f}ms")
    
    print("\n🎯 Throughput:")
    print(f"   Requests/sec: {stats.total.total_rps:.2f}")
    
    # Performance thresholds
    print("\n✅ Performance Analysis:")
    if stats.total.avg_response_time < 500:
        print("   ✅ Average response time: EXCELLENT")
    elif stats.total.avg_response_time < 1000:
        print("   ⚠️  Average response time: ACCEPTABLE")
    else:
        print("   ❌ Average response time: NEEDS IMPROVEMENT")
    
    if stats.total.fail_ratio < 0.01:
        print("   ✅ Error rate: EXCELLENT (<1%)")
    elif stats.total.fail_ratio < 0.05:
        print("   ⚠️  Error rate: ACCEPTABLE (<5%)")
    else:
        print("   ❌ Error rate: TOO HIGH (>5%)")
    
    print("\n" + "="*70 + "\n")


# ==================== Custom Stats ====================
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track custom metrics cho mỗi request"""
    if exception:
        print(f"❌ Request failed: {name} - {exception}")
    elif response_time > 2000:
        print(f"⚠️  Slow request detected: {name} - {response_time}ms")