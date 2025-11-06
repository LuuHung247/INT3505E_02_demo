import pytest
import json
from datetime import datetime, timedelta
import jwt
from app import app, Book
from mongoengine import connect, disconnect
from mongomock import MongoClient

# ==================== FIXTURES ====================
@pytest.fixture(scope='function')
def client():
    """Tạo test client và mock database"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret'
    
    # Disconnect existing connection and connect to mongomock
    disconnect()
    connect('mongoenginetest', host='mongodb://localhost', mongo_client_class=MongoClient)
    
    with app.test_client() as client:
        yield client
    
    # Cleanup
    Book.drop_collection()
    disconnect()

@pytest.fixture
def auth_token():
    """Tạo JWT token cho testing"""
    token = jwt.encode({
        'user': 'admin',
        'exp': datetime.utcnow() + timedelta(minutes=30)
    }, 'test_secret', algorithm="HS256")
    return token

@pytest.fixture
def auth_headers(auth_token):
    """Tạo headers với authorization"""
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }

@pytest.fixture
def sample_books():
    """Tạo dữ liệu mẫu"""
    books = [
        Book(title="Clean Code", author="Robert Martin", available=True),
        Book(title="Design Patterns", author="Gang of Four", available=True),
        Book(title="Refactoring", author="Martin Fowler", available=False)
    ]
    for book in books:
        book.save()
    return books


# ==================== UNIT TESTS - AUTH ====================
class TestAuthentication:
    """Test các chức năng authentication"""
    
    def test_login_success(self, client):
        """Test đăng nhập thành công"""
        response = client.post('/api/v1/login', 
            json={'username': 'admin', 'password': '123456'})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'token' in data['data']
        assert data['message'] == 'Login successful'
    
    def test_login_invalid_credentials(self, client):
        """Test đăng nhập sai thông tin"""
        response = client.post('/api/v1/login',
            json={'username': 'wrong', 'password': 'wrong'})
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['message'] == 'Invalid credentials'
    
    def test_access_without_token(self, client):
        """Test truy cập API không có token"""
        response = client.get('/api/v1/books')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['message'] == 'Token is missing'
    
    def test_access_with_invalid_token(self, client):
        """Test truy cập với token không hợp lệ"""
        headers = {'Authorization': 'Bearer invalid_token'}
        response = client.get('/api/v1/books', headers=headers)
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['message'] == 'Invalid token'
    
    def test_access_with_expired_token(self, client):
        """Test truy cập với token hết hạn"""
        expired_token = jwt.encode({
            'user': 'admin',
            'exp': datetime.utcnow() - timedelta(minutes=1)
        }, 'test_secret', algorithm="HS256")
        
        headers = {'Authorization': f'Bearer {expired_token}'}
        response = client.get('/api/v1/books', headers=headers)
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['message'] == 'Token expired'


# ==================== UNIT TESTS - BOOKS CRUD ====================
class TestBooksCRUD:
    """Test các chức năng CRUD của Books"""
    
    def test_get_all_books_empty(self, client, auth_headers):
        """Test lấy danh sách khi chưa có sách"""
        response = client.get('/api/v1/books', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert len(data['data']['books']) == 0
    
    def test_get_all_books(self, client, auth_headers, sample_books):
        """Test lấy danh sách tất cả sách"""
        response = client.get('/api/v1/books', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']['books']) == 3
        assert 'ETag' in response.headers
    
    def test_create_book_success(self, client, auth_headers):
        """Test tạo sách mới thành công"""
        new_book = {
            'title': 'Test Driven Development',
            'author': 'Kent Beck'
        }
        response = client.post('/api/v1/books', 
            headers=auth_headers, json=new_book)
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['data']['title'] == new_book['title']
        assert data['data']['available'] == True
        assert '_id' in data['data']
    
    def test_create_book_missing_fields(self, client, auth_headers):
        """Test tạo sách thiếu thông tin"""
        response = client.post('/api/v1/books',
            headers=auth_headers, json={'title': 'Only Title'})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Missing title or author' in data['message']
    
    def test_get_book_by_id(self, client, auth_headers, sample_books):
        """Test lấy thông tin 1 sách theo ID"""
        book_id = str(sample_books[0].id)
        response = client.get(f'/api/v1/books/{book_id}', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['_id'] == book_id
        assert data['data']['title'] == 'Clean Code'
    
    def test_get_book_not_found(self, client, auth_headers):
        """Test lấy sách không tồn tại"""
        fake_id = '507f1f77bcf86cd799439011'
        response = client.get(f'/api/v1/books/{fake_id}', headers=auth_headers)
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['message'] == 'Book not found'
    
    def test_update_book(self, client, auth_headers, sample_books):
        """Test cập nhật thông tin sách"""
        book_id = str(sample_books[0].id)
        update_data = {
            'title': 'Clean Code Updated',
            'available': False
        }
        response = client.put(f'/api/v1/books/{book_id}',
            headers=auth_headers, json=update_data)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['title'] == 'Clean Code Updated'
        assert data['data']['available'] == False
    
    def test_delete_book(self, client, auth_headers, sample_books):
        """Test xóa sách"""
        book_id = str(sample_books[0].id)
        response = client.delete(f'/api/v1/books/{book_id}', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['message'] == 'Book deleted'
        
        # Verify book is deleted
        get_response = client.get(f'/api/v1/books/{book_id}', headers=auth_headers)
        assert get_response.status_code == 404


# ==================== UNIT TESTS - FILTERING ====================
class TestBookFiltering:
    """Test các chức năng filter và search"""
    
    def test_filter_by_available(self, client, auth_headers, sample_books):
        """Test lọc sách còn/hết"""
        response = client.get('/api/v1/books?available=true', headers=auth_headers)
        
        data = json.loads(response.data)
        books = data['data']['books']
        assert all(book['available'] == True for book in books)
        assert len(books) == 2
    
    def test_search_by_title(self, client, auth_headers, sample_books):
        """Test tìm kiếm theo tên sách"""
        response = client.get('/api/v1/books?title=Clean', headers=auth_headers)
        
        data = json.loads(response.data)
        books = data['data']['books']
        assert len(books) == 1
        assert 'Clean' in books[0]['title']
    
    def test_search_by_author(self, client, auth_headers, sample_books):
        """Test tìm kiếm theo tác giả"""
        response = client.get('/api/v1/books?author=Martin', headers=auth_headers)
        
        data = json.loads(response.data)
        books = data['data']['books']
        assert len(books) == 2  # Robert Martin và Martin Fowler
    
    def test_combined_filters(self, client, auth_headers, sample_books):
        """Test kết hợp nhiều filter"""
        response = client.get('/api/v1/books?available=true&author=Martin',
            headers=auth_headers)
        
        data = json.loads(response.data)
        books = data['data']['books']
        assert len(books) == 1
        assert books[0]['available'] == True
        assert 'Martin' in books[0]['author']


# ==================== INTEGRATION TESTS - ETAG ====================
class TestETagCaching:
    """Test cơ chế ETag caching"""
    
    def test_etag_generated(self, client, auth_headers, sample_books):
        """Test ETag được tạo"""
        response = client.get('/api/v1/books', headers=auth_headers)
        assert 'ETag' in response.headers
        assert 'Cache-Control' in response.headers
    
    def test_etag_not_modified(self, client, auth_headers, sample_books):
        """Test 304 Not Modified khi ETag match"""
        book_id = str(sample_books[0].id)
        
        # First request
        response1 = client.get(f'/api/v1/books/{book_id}', headers=auth_headers)
        etag = response1.headers.get('ETag')
        
        # Second request with ETag
        headers_with_etag = auth_headers.copy()
        headers_with_etag['If-None-Match'] = etag
        response2 = client.get(f'/api/v1/books/{book_id}', headers=headers_with_etag)
        
        assert response2.status_code == 304
        assert len(response2.data) == 0


# ==================== INTEGRATION TESTS - WORKFLOW ====================
class TestCompleteWorkflow:
    """Test workflow hoàn chỉnh"""
    
    def test_complete_book_lifecycle(self, client, auth_headers):
        """Test quy trình đầy đủ: tạo -> đọc -> sửa -> xóa"""
        
        # 1. Tạo sách mới
        new_book = {'title': 'Integration Test Book', 'author': 'Test Author'}
        create_response = client.post('/api/v1/books',
            headers=auth_headers, json=new_book)
        assert create_response.status_code == 201
        book_id = json.loads(create_response.data)['data']['_id']
        
        # 2. Đọc sách vừa tạo
        get_response = client.get(f'/api/v1/books/{book_id}', headers=auth_headers)
        assert get_response.status_code == 200
        book_data = json.loads(get_response.data)['data']
        assert book_data['title'] == 'Integration Test Book'
        
        # 3. Cập nhật sách
        update_data = {'available': False}
        update_response = client.put(f'/api/v1/books/{book_id}',
            headers=auth_headers, json=update_data)
        assert update_response.status_code == 200
        
        # 4. Verify cập nhật
        verify_response = client.get(f'/api/v1/books/{book_id}', headers=auth_headers)
        updated_book = json.loads(verify_response.data)['data']
        assert updated_book['available'] == False
        
        # 5. Xóa sách
        delete_response = client.delete(f'/api/v1/books/{book_id}', headers=auth_headers)
        assert delete_response.status_code == 200
        
        # 6. Verify đã xóa
        final_response = client.get(f'/api/v1/books/{book_id}', headers=auth_headers)
        assert final_response.status_code == 404


# ==================== RUN TESTS ====================
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=app', '--cov-report=html'])