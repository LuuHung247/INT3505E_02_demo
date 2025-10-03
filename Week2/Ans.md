## Đề bài

- Khi nào thì việc cache dữ liệu có lợi? Khi nào lại có thể gây hại?

- HTTP header nào giúp kiểm soát cache? Hãy tìm hiểu ít nhất 3 header.

- Xây dựng API trả về thông tin trạng thái của vài cuốn sách và thiết lập cache 10 phút. Làm thế nào để đảm bảo client không nhận dữ liệu cũ khi có người mượn sách?

- Sử dụng ETag để implement conditional requests. Demo việc giảm bandwidth.

- Hết 10 phút thì sẽ refresh như thế nào?

## Câu trả lời

### 1) Khi nào cache có lợi / khi nào gây hại

**Lợi:**

- Giảm độ trễ (Latency):

  - Thay vì mỗi yêu cầu (request) phải đi một chặng đường dài đến máy chủ gốc (origin server), nó sẽ được phục vụ từ một lớp cache ở gần người dùng hơn (ví dụ: CDN, Reverse Proxy). Người dùng nhận được phản hồi gần như tức thì, cải thiện đáng kể trải nghiệm người dùng, đặc biệt với các tài nguyên tĩnh.

- Giảm tải backend:

  - Cache đóng vai trò như một "lá chắn" cho máy chủ gốc. Những yêu cầu lặp đi lặp lại cho cùng một dữ liệu sẽ được cache xử lý. Nhờ vậy, máy chủ gốc chỉ phải làm việc khi có yêu cầu mới hoặc khi dữ liệu trong cache đã hết hạn.

- Tiết kiệm băng thông và chi phí:

  - Bằng cách phục vụ nội dung từ cache gần người dùng, lượng dữ liệu phải truyền đi từ máy chủ gốc qua các mạng đường dài sẽ giảm đi đáng kể. Chỉ có một lần truyền từ máy chủ gốc đến cache, sau đó cache sẽ phục vụ cho hàng ngàn, thậm chí hàng triệu yêu cầu từ người dùng.

- Tăng khả năng chịu tải (scale):

  - Khi phần lớn các yêu cầu đã được cache xử lý, máy chủ gốc sẽ được "giải phóng" để tập trung vào các tác vụ quan trọng không thể cache được (ví dụ: xử lý giao dịch thanh toán, cập nhật thông tin người dùng).

**Hại:**

- Dữ liệu nhạy cảm có thể bị trả dữ liệu cũ:
  - Khi cache được dùng để lưu trữ dữ liệu nhạy cảm, ví dụ như số dư tài khoản ngân hàng, trạng thái mượn sách trên thư viện hoặc thông tin cá nhân, nếu cache không được cập nhật kịp thời hoặc bị thiết lập thời gian sống (TTL) dài, client có thể nhận lại dữ liệu cũ. Điều này dẫn đến việc người dùng nhìn thấy thông tin không chính xác, thậm chí có thể gây ra sai sót trong giao dịch tài chính, đặt sách hoặc các quyết định dựa trên dữ liệu.
- Sai cấu hình header daaxn cache trả dữ liệu không mong muốn (ví dụ cache response chứa token).
- Phức tạp khi cần invalidation (xóa cache) — nếu không có cơ chế purge, client/proxy có thể giữ dữ liệu cũ lâu.
- Khi cần tính chất “real-time” (kết quả cập nhật tức thì) mà cache che lấp cập nhật.

### 2) HTTP headers giúp kiểm soát cache (ít nhất 3)

1. **Cache-Control** — cơ bản và mạnh mẽ nhất. Ví dụ:

   - `Cache-Control: public, max-age=600` (cho phép cache công cộng, lưu 600s)
   - `Cache-Control: private, max-age=0, no-cache` (không cho proxy cache; bắt client revalidate)
   - `Cache-Control: s-maxage=600` (dành cho shared caches / proxy)

2. **ETag** — một giá trị (token) đại diện cho phiên bản resource (ví dụ hash). Dùng để revalidation (If-None-Match).
3. **If-None-Match** (request header) — client/proxy gửi ETag trước đó để hỏi server: “nếu chưa thay đổi thì trả 304”.
4. **Last-Modified** / **If-Modified-Since** — cách khác để revalidate dựa trên timestamp.
5. **Expires** — ngày hết hạn cũ (hiện nay thường dùng Cache-Control).
   (Đã liệt kê trên 3 header; tập trung dùng `Cache-Control`, `ETag`, `If-None-Match` cho ví dụ.)
