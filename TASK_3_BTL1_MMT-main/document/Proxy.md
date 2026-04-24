# Proxy

**Proxy (máy chủ ủy quyền)** là một thành phần trung gian giữa **client** và **server thực (backend)**.  
Khi client gửi yêu cầu (request), thay vì đi thẳng đến backend, yêu cầu sẽ đi qua Proxy. Proxy sau đó:  

1. **Nhận yêu cầu từ client.**  
2. **Xác định backend phù hợp** để xử lý (dựa trên địa chỉ Host hoặc quy tắc định sẵn).  
3. **Chuyển tiếp yêu cầu đến backend.**  
4. **Nhận phản hồi từ backend và trả lại cho client.**

![](https://www.indusface.com/wp-content/uploads/2023/04/Forward-proxy-vs-reverse-proxy-1.png)

Nhờ vậy, Proxy giúp:
- **Ẩn backend thật** khỏi client.  
- **Cân bằng tải (Load Balancing):** chia đều lưu lượng giữa nhiều backend.  
- **Tăng bảo mật:** có thể lọc hoặc kiểm soát request.  
- **Dễ mở rộng:** thêm backend mà không cần thay đổi client.  


## Code

```py
HOSTS = {
    "app.local": {
        "backends": ["backend1:9001", "backend2:9001", "app:9001"],
        "policy": "round-robin",
        "index": 0
    },
}
```

| Thành phần    | Ý nghĩa                                                                                                                                                   |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `"app.local"` | Tên **Host** được client gửi trong HTTP Header (`Host: app.local`). Proxy dựa vào đây để xác định backend đích.                                           |
| `"backends"`  | Danh sách các backend server có thể xử lý yêu cầu cho host này. Ở đây có 3 server: `backend1`, `backend2`, và `app` — tất cả đều lắng nghe ở port `9001`. |
| `"policy"`    | Chính sách phân phối tải. Ở đây là **`round-robin`**, nghĩa là proxy sẽ **luân phiên gửi** các request đến từng backend trong danh sách.                  |
| `"index"`     | Biến đếm nội bộ để theo dõi lần gửi tiếp theo trong cơ chế round-robin. Mỗi khi proxy chọn một backend, nó sẽ tăng `index` lên 1.                         |

### ⚙️ Cách hoạt động

Khi client gửi request với `Host: app.local`,  
→ Proxy sẽ tìm thấy cấu hình tương ứng trong `HOSTS`.

Proxy đọc danh sách `backends` và chính sách `round-robin` để quyết định backend nào sẽ xử lý request tiếp theo.

**Ví dụ minh họa:**

| Lượt Request | Backend được chọn |
|---------------|-------------------|
| Request 1 | `backend1:9001` |
| Request 2 | `backend2:9001` |
| Request 3 | `app:9001` |
| Request 4 | `backend1:9001` |

Nhờ cơ chế **round-robin**, proxy sẽ luân phiên gửi các request đến từng backend, giúp **cân bằng tải** giữa nhiều server mà **client không cần biết sự tồn tại của chúng**.