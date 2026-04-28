# ComputerNetwork_Assignment

Assignment 1 - Implement non-blocking HTTP server, authentication, proxy, and hybrid chat application.

## Chức năng chính
- HTTP server non-blocking
- Authentication bằng username/password
- Session bằng cookie
- Tracker quản lý danh sách peer
- Peer-to-peer direct message
- Broadcast message
- Web UI cho chat
- Proxy + round-robin

## Tài khoản demo
- alice / 123
- bob / 123
- charlie / 123
- dave / 123

## Cấu trúc chạy local
- Tracker: 9000
- Alice: HTTP 9001, P2P 9101
- Bob: HTTP 9002, P2P 9102
- Charlie: HTTP 9003, P2P 9103
- Dave: HTTP 9004, P2P 9104
- Proxy: 8080

## Lưu ý IP
- Nếu test trên 1 máy: dùng 127.0.0.1
- Nếu test trên nhiều máy LAN:
  - đổi APP_IP theo IP thật của từng máy
  - đổi TRACKER_BASE trong static/js/chat.js thành IP của máy tracker
  - khi gọi /submit-info, phải khai báo đúng ip + port thật

---

## 1. Xóa process cũ
Chạy PowerShell:

```powershell
9000,9001,9002,9003,9004,8080,9100,9101,9102,9103,9104 | ForEach-Object {
  Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force }
}
```

Kiểm tra lại:

```powershell
Get-NetTCPConnection -LocalPort 9000,9001,9002,9003,9004,8080,9100,9101,9102,9103,9104 -ErrorAction SilentlyContinue
```

---

## 2. Start hệ thống

### Tracker
```powershell
$env:APP_MODE="tracker"
$env:APP_IP="127.0.0.1"
$env:P2P_PORT="9100"
$env:INSTANCE_ID="tracker"
py start_sampleapp.py --server-ip 127.0.0.1 --server-port 9000 --mode tracker
```

### Alice
```powershell
$env:APP_MODE="peer"
$env:APP_IP="127.0.0.1"
$env:P2P_PORT="9101"
$env:INSTANCE_ID="alice"
py start_sampleapp.py --server-ip 127.0.0.1 --server-port 9001 --mode peer
```

### Bob
```powershell
$env:APP_MODE="peer"
$env:APP_IP="127.0.0.1"
$env:P2P_PORT="9102"
$env:INSTANCE_ID="bob"
py start_sampleapp.py --server-ip 127.0.0.1 --server-port 9002 --mode peer
```

### Charlie
```powershell
$env:APP_MODE="peer"
$env:APP_IP="127.0.0.1"
$env:P2P_PORT="9103"
$env:INSTANCE_ID="charlie"
py start_sampleapp.py --server-ip 127.0.0.1 --server-port 9003 --mode peer
```

### Dave
```powershell
$env:APP_MODE="peer"
$env:APP_IP="127.0.0.1"
$env:P2P_PORT="9104"
$env:INSTANCE_ID="dave"
py start_sampleapp.py --server-ip 127.0.0.1 --server-port 9004 --mode peer
```

Kiểm tra port đã lên:

```powershell
Get-NetTCPConnection -LocalPort 9000,9001,9002,9003,9004 -State Listen
```

---

## 3. Register peers lên tracker

### Alice
```powershell
$body = @{
  username = "alice"
  ip = "127.0.0.1"
  port = 9101
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:9000/submit-info" -Method POST -ContentType "application/json" -Body $body
```

### Bob
```powershell
$body = @{
  username = "bob"
  ip = "127.0.0.1"
  port = 9102
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:9000/submit-info" -Method POST -ContentType "application/json" -Body $body
```

### Charlie
```powershell
$body = @{
  username = "charlie"
  ip = "127.0.0.1"
  port = 9103
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:9000/submit-info" -Method POST -ContentType "application/json" -Body $body
```

### Dave
```powershell
$body = @{
  username = "dave"
  ip = "127.0.0.1"
  port = 9104
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:9000/submit-info" -Method POST -ContentType "application/json" -Body $body
```

### Kiểm tra tracker
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:9000/get-list" -Method GET | ConvertTo-Json -Depth 6
```

---

## 4. Test Login / Logout

### Mở login page
- http://127.0.0.1:9001/login.html
- http://127.0.0.1:9002/login.html
- http://127.0.0.1:9003/login.html
- http://127.0.0.1:9004/login.html

### Test login đúng
Ví dụ:
- username: alice
- password: 123

Kết quả:
- vào được index.html
- góc trên hiển thị đúng tên user

### Test login sai
Ví dụ:
- username: alice
- password: 999

Kết quả:
- không vào được
- hiện lỗi đăng nhập

### Test logout
- login thành công
- bấm nút Logout
- hệ thống quay về login.html
- mở lại index.html khi chưa login sẽ bị chuyển về login.html

### Test login bằng PowerShell
```powershell
$body = @{
  username = "alice"
  password = "123"
} | ConvertTo-Json

$r = Invoke-WebRequest -Uri "http://127.0.0.1:9001/login" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -SessionVariable s1

$r.Content
$r.Headers["Set-Cookie"]
```

### Kiểm tra /me
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:9001/me" `
  -Method GET `
  -WebSession $s1 | ConvertTo-Json -Depth 6
```

### Logout bằng PowerShell
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:9001/logout" `
  -Method POST `
  -WebSession $s1 | ConvertTo-Json -Depth 6
```

### Kiểm tra /me sau logout
```powershell
try {
  Invoke-WebRequest -Uri "http://127.0.0.1:9001/me" -Method GET -WebSession $s1
} catch {
  $resp = $_.Exception.Response
  [int]$resp.StatusCode
}
```

---

## 5. Test API chat

### Direct message: Alice -> Bob
```powershell
$body = @{
  sender = "alice"
  channel = "general"
  ip = "127.0.0.1"
  port = 9102
  message = "hello bob api"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:9001/send-peer" -Method POST -ContentType "application/json" -Body $body
```

### Bob đọc messages
```powershell
$check = @{
  channel = "general"
  after_seq = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:9002/messages" -Method POST -ContentType "application/json" -Body $check | ConvertTo-Json -Depth 6
```

### Broadcast: Alice -> tất cả
```powershell
$body = @{
  sender = "alice"
  channel = "general"
  message = "hello everyone api"
  peers = @(
    @{ username = "bob"; ip = "127.0.0.1"; port = 9102 },
    @{ username = "charlie"; ip = "127.0.0.1"; port = 9103 },
    @{ username = "dave"; ip = "127.0.0.1"; port = 9104 }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:9001/broadcast-peer" -Method POST -ContentType "application/json" -Body $body
```

### Bob / Charlie / Dave đọc messages
```powershell
$check = @{
  channel = "general"
  after_seq = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:9002/messages" -Method POST -ContentType "application/json" -Body $check | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "http://127.0.0.1:9003/messages" -Method POST -ContentType "application/json" -Body $check | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "http://127.0.0.1:9004/messages" -Method POST -ContentType "application/json" -Body $check | ConvertTo-Json -Depth 6
```

---

## 6. Test UI chat

### Mở các tab
- http://127.0.0.1:9001/index.html
- http://127.0.0.1:9002/index.html
- http://127.0.0.1:9003/index.html
- http://127.0.0.1:9004/index.html

### Nếu cần set username trong browser console
Nếu browser chặn paste, gõ trước:
```javascript
allow pasting
```

#### Alice
```javascript
localStorage.setItem("chat_username", "alice");
location.reload();
```

#### Bob
```javascript
localStorage.setItem("chat_username", "bob");
location.reload();
```

#### Charlie
```javascript
localStorage.setItem("chat_username", "charlie");
location.reload();
```

#### Dave
```javascript
localStorage.setItem("chat_username", "dave");
location.reload();
```

### Checklist UI
- bấm Refresh Peers
- Alice thấy Bob / Charlie / Dave
- Bob thấy Alice / Charlie / Dave
- click peer để vào direct mode
- bỏ chọn peer để quay lại broadcast/general
- direct message giữa 2 peer hoạt động
- broadcast từ 1 peer thì các peer còn lại đều nhận
- chuyển peer / channel thì cửa sổ chat đổi đúng

---

## 7. Test proxy

### Start proxy
```powershell
py start_proxy.py --server-ip 127.0.0.1 --server-port 8080
```

### Lưu ý cho máy khác IP
Trong config/proxy.conf, phải sửa proxy_pass theo IP thật của tracker / peer.
Nếu tracker ở máy khác, không được để 127.0.0.1.

### Test tracker qua proxy
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/get-list" `
  -Method GET `
  -Headers @{ Host = "127.0.0.1:8080" } | ConvertTo-Json -Depth 6
```

### Test app qua proxy
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/self-info" `
  -Method GET `
  -Headers @{ Host = "app1.local" } | ConvertTo-Json -Depth 6
```

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/self-info" `
  -Method GET `
  -Headers @{ Host = "app2.local" } | ConvertTo-Json -Depth 6
```

---

## 8. Test cookie / session qua proxy

### Login qua proxy
```powershell
$body = @{
  username = "alice"
  password = "123"
} | ConvertTo-Json

$r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/login" `
  -Method POST `
  -Headers @{ Host = "127.0.0.1:8080" } `
  -ContentType "application/json" `
  -Body $body `
  -SessionVariable sProxy

$r.Content
$r.Headers["Set-Cookie"]
```

### /me qua proxy
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/me" `
  -Method GET `
  -Headers @{ Host = "127.0.0.1:8080" } `
  -WebSession $sProxy | ConvertTo-Json -Depth 6
```

### Logout qua proxy
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/logout" `
  -Method POST `
  -Headers @{ Host = "127.0.0.1:8080" } `
  -WebSession $sProxy | ConvertTo-Json -Depth 6
```

---

## 9. Test round-robin

Phần này nên test riêng, không chạy chung với map 4 peer UI nếu trùng cổng 9002/9003.

Proxy config cần có rr.local trỏ tới 2 backend khác nhau.

```powershell
1..8 | ForEach-Object {
  Invoke-RestMethod -Uri "http://127.0.0.1:8080/instance" `
    -Method GET `
    -Headers @{ Host = "rr.local" } | ConvertTo-Json -Compress
}
```

Kỳ vọng:
- request được phân phối luân phiên giữa 2 instance

---

## 10. Checklist PASS cuối cùng
- tracker start thành công
- peers register đúng lên tracker
- self-info đúng port / mode
- direct API pass
- broadcast API pass
- UI refresh peers pass
- UI direct pass
- UI broadcast pass
- chuyển peer / channel đúng
- login / me / logout pass
- proxy routing pass
- round-robin pass nếu nhóm có demo phần đó

---

## 11. Lỗi thường gặp

### WinError 10049
- bind sai IP
- dùng 127.0.0.1 để test local
- hoặc đổi sang IP LAN đúng

### Port already in use
- cổng HTTP hoặc P2P đang bị process cũ chiếm
- chạy lại phần Xóa process cũ

### Peers không hiện trên UI
- kiểm tra TRACKER_BASE
- kiểm tra /submit-info
- bấm Refresh Peers

### Tên user trên UI không khớp backend
- kiểm tra localStorage ở đúng tab / đúng port

### Broadcast bị double text ở sender
- để server echo render 1 lần duy nhất
- không local-add broadcast thêm lần nữa

### CORS lỗi khi gọi tracker khác origin
- không dùng credentials: include cho tracker fetch nếu không cần cookie tracker

---

## 12. Ghi chú khi demo
- nên dùng tab ẩn danh (Incognito / Private Window) để tránh cookie cũ
- nếu thấy hành vi lạ:
  - xóa cache
  - đóng tab cũ
  - login lại
- khi test nhiều máy, luôn kiểm tra lại:
  - APP_IP
  - P2P_PORT
  - TRACKER_BASE
  - proxy.conf
