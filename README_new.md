# ComputerNetwork_Assignment

Assignment 1 – Implement a non-blocking HTTP server, authentication, proxy, and hybrid chat application.

## Main Features
- Non-blocking HTTP server
- Username/password authentication
- Cookie-based session management
- Tracker for peer registration and discovery
- Peer-to-peer direct messaging
- Broadcast messaging
- Web UI for chat
- Proxy with host-based routing
- Optional round-robin routing
- Dynamic proxy peer resolution through tracker

## Demo Accounts
- `alice / 123`
- `bob / 123`

## Demo Topology
### Fixed machine
- **Tracker**: `192.168.208.150:9000`
- **Proxy** (optional): `192.168.208.150:8080`

### Dynamic peer machines
- **Alice machine**: dynamic IP from current Wi-Fi/LAN, HTTP `9001`, P2P `9101`
- **Bob machine**: dynamic IP from current Wi-Fi/LAN, HTTP `9002`, P2P `9102`

## Important Notes Before Running

### 1. Backend mode
This project uses:
- **coroutine mode** for the backend/web application layer
- **threading mode** for the proxy layer

### 2. `static/js/chat.js`
Make sure `TRACKER_BASE` points to the tracker machine:

```javascript
const TRACKER_BASE = "http://192.168.208.150:9000";
```

### 3. About proxy mode
This README assumes you are using the **dynamic tracker-based proxy** version of `proxy.py`.

That means:
- the tracker route is still static
- peer backends such as Alice/Bob are resolved dynamically from tracker `/get-list`
- if Alice/Bob changes Wi-Fi/LAN IP, you do **not** need to rewrite peer IPs in `proxy.conf`
- however, the peer must **restart and register again** with the tracker after its IP changes

### 4. About `proxy.conf`
With the dynamic proxy version, you only need static config for:
- tracker
- optional round-robin hosts

Example minimal config:

```conf
host "192.168.208.150:8080" {
    proxy_pass http://192.168.208.150:9000;
}

host "rr.local" {
    proxy_pass http://192.168.73.196:9001;
    proxy_pass http://192.168.73.24:9002;
    dist_policy round-robin;
}
```

Peer hosts such as:
- `alice.192.168.208.150.nip.io:8080`
- `bob.192.168.208.150.nip.io:8080`

will be resolved dynamically by proxy through tracker lookup.

### 5. Current proxy assumption
The dynamic proxy currently infers HTTP port from registered P2P port using:

- `9101 -> 9001`
- `9102 -> 9002`

So if you change the port convention, update proxy logic or store `http_port` in tracker.

---

## 0. Clean old processes

Run this on each machine before demo:

```powershell
9000,9001,9002,8080,9100,9101,9102 | ForEach-Object {
  Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force }
}
```

Check again:

```powershell
Get-NetTCPConnection -LocalPort 9000,9001,9002,8080,9100,9101,9102 -ErrorAction SilentlyContinue
```

## 1. Start the system

### Tracker machine — `192.168.208.150`

```powershell
$env:APP_MODE="tracker"
$env:APP_IP="192.168.208.150"
$env:P2P_PORT="9100"
$env:INSTANCE_ID="tracker"
py start_sampleapp.py --server-ip 192.168.208.150 --server-port 9000 --mode tracker
```

---

## 2. Get current dynamic IP on peer machines

Run this on **Alice machine** or **Bob machine**.  
It returns the local IP that the machine currently uses to reach the tracker.

```powershell
$trackerIp = "192.168.208.150"

$udp = New-Object System.Net.Sockets.Socket(
  [System.Net.Sockets.AddressFamily]::InterNetwork,
  [System.Net.Sockets.SocketType]::Dgram,
  [System.Net.Sockets.ProtocolType]::Udp
)

$udp.Connect($trackerIp, 9000)
$myIP = ($udp.LocalEndPoint).Address.IPAddressToString
$udp.Close()

$myIP
```

> If this prints `192.168.208.150`, you are running the command on the tracker machine.

---

## 3. Start Alice

### On Alice machine

```powershell
$trackerIp = "192.168.208.150"

$udp = New-Object System.Net.Sockets.Socket(
  [System.Net.Sockets.AddressFamily]::InterNetwork,
  [System.Net.Sockets.SocketType]::Dgram,
  [System.Net.Sockets.ProtocolType]::Udp
)
$udp.Connect($trackerIp, 9000)
$myIP = ($udp.LocalEndPoint).Address.IPAddressToString
$udp.Close()

$env:APP_MODE="peer"
$env:APP_IP=$myIP
$env:P2P_PORT="9101"
$env:INSTANCE_ID="alice"

py start_sampleapp.py --server-ip $myIP --server-port 9001 --p2p-port 9101 --mode peer
```

### Register Alice to tracker

```powershell
$trackerIp = "192.168.208.150"

$udp = New-Object System.Net.Sockets.Socket(
  [System.Net.Sockets.AddressFamily]::InterNetwork,
  [System.Net.Sockets.SocketType]::Dgram,
  [System.Net.Sockets.ProtocolType]::Udp
)
$udp.Connect($trackerIp, 9000)
$myIP = ($udp.LocalEndPoint).Address.IPAddressToString
$udp.Close()

$body = @{
  username = "alice"
  ip = $myIP
  port = 9101
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://$trackerIp:9000/submit-info" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

---

## 4. Start Bob

### On Bob machine

```powershell
$trackerIp = "192.168.208.150"

$udp = New-Object System.Net.Sockets.Socket(
  [System.Net.Sockets.AddressFamily]::InterNetwork,
  [System.Net.Sockets.SocketType]::Dgram,
  [System.Net.Sockets.ProtocolType]::Udp
)
$udp.Connect($trackerIp, 9000)
$myIP = ($udp.LocalEndPoint).Address.IPAddressToString
$udp.Close()

$env:APP_MODE="peer"
$env:APP_IP=$myIP
$env:P2P_PORT="9102"
$env:INSTANCE_ID="bob"

py start_sampleapp.py --server-ip $myIP --server-port 9002 --p2p-port 9102 --mode peer
```

### Register Bob to tracker

```powershell
$trackerIp = "192.168.208.150"

$udp = New-Object System.Net.Sockets.Socket(
  [System.Net.Sockets.AddressFamily]::InterNetwork,
  [System.Net.Sockets.SocketType]::Dgram,
  [System.Net.Sockets.ProtocolType]::Udp
)
$udp.Connect($trackerIp, 9000)
$myIP = ($udp.LocalEndPoint).Address.IPAddressToString
$udp.Close()

$body = @{
  username = "bob"
  ip = $myIP
  port = 9102
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://$trackerIp:9000/submit-info" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

---

## 5. Verify tracker list

Run on tracker machine or any machine that can reach tracker:

```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:9000/get-list" -Method GET | ConvertTo-Json -Depth 6
```

Expected:
- `alice` appears with Alice’s current IP
- `bob` appears with Bob’s current IP

---

## 6. Test login / logout directly

### Open login pages directly
- Alice: `http://<Alice_Current_IP>:9001/login.html`
- Bob: `http://<Bob_Current_IP>:9002/login.html`

### Successful login
Example:
- username: `alice`
- password: `123`

Expected:
- browser enters `index.html`
- top bar shows correct username

### Failed login
Example:
- username: `alice`
- password: `999`

Expected:
- login fails
- error is shown on screen

### Logout
- login first
- click `Logout`
- browser returns to `login.html`
- opening `index.html` without valid session redirects to login page

---

## 7. Test login by PowerShell

### Alice

```powershell
$body = @{
  username = "alice"
  password = "123"
} | ConvertTo-Json

$r = Invoke-WebRequest -Uri "http://<Alice_Current_IP>:9001/login" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -SessionVariable sAlice

$r.Content
$r.Headers["Set-Cookie"]
```

### Check `/me`

```powershell
Invoke-RestMethod -Uri "http://<Alice_Current_IP>:9001/me" `
  -Method GET `
  -WebSession $sAlice | ConvertTo-Json -Depth 6
```

### Logout

```powershell
Invoke-RestMethod -Uri "http://<Alice_Current_IP>:9001/logout" `
  -Method POST `
  -WebSession $sAlice | ConvertTo-Json -Depth 6
```

---

## 8. Test API chat

### Alice sends direct message to Bob
Run on Alice machine:

```powershell
$bobIp = "<Bob_Current_IP>"

$body = @{
  sender = "alice"
  to = "bob"
  channel = "dm:alice:bob"
  ip = $bobIp
  port = 9102
  message = "hello bob api"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://<Alice_Current_IP>:9001/send-peer" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

### Bob reads messages
Run on Bob machine:

```powershell
$check = @{
  channel = "__all__"
  after_seq = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://<Bob_Current_IP>:9002/messages" `
  -Method POST `
  -ContentType "application/json" `
  -Body $check | ConvertTo-Json -Depth 6
```

### Broadcast: Alice -> Bob
Run on Alice machine:

```powershell
$bobIp = "<Bob_Current_IP>"

$body = @{
  sender = "alice"
  channel = "general"
  message = "hello bob broadcast"
  peers = @(
    @{ username = "bob"; ip = $bobIp; port = 9102 }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://<Alice_Current_IP>:9001/broadcast-peer" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

---

## 9. Test UI chat directly

### Open UI directly
- Alice: `http://<Alice_Current_IP>:9001/index.html`
- Bob: `http://<Bob_Current_IP>:9002/index.html`

### UI checklist
- click `Refresh Peers`
- Alice sees Bob
- Bob sees Alice
- click a peer to enter direct mode
- direct message works
- broadcast from Alice is received by Bob
- logout works
- page refresh keeps login if session cookie is still valid

---

## 10. Test proxy (dynamic tracker-based proxy)

### Start proxy
Run on tracker machine:

```powershell
py start_proxy.py --server-ip 192.168.208.150 --server-port 8080
```

### What stays static in `proxy.conf`
You only need:
- tracker route
- optional round-robin route

Example:

```conf
host "192.168.208.150:8080" {
    proxy_pass http://192.168.208.150:9000;
}

host "rr.local" {
    proxy_pass http://192.168.73.196:9001;
    proxy_pass http://192.168.73.24:9002;
    dist_policy round-robin;
}
```

### What becomes dynamic
These peer hosts do **not** need static mapping in `proxy.conf`:
- `alice.192.168.208.150.nip.io:8080`
- `bob.192.168.208.150.nip.io:8080`

The proxy resolves them dynamically using tracker `/get-list`.

### Test tracker via proxy

```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/get-list" `
  -Method GET `
  -Headers @{ Host = "192.168.208.150:8080" } | ConvertTo-Json -Depth 6
```

### Test Alice app via proxy

```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/self-info" `
  -Method GET `
  -Headers @{ Host = "alice.192.168.208.150.nip.io:8080" } | ConvertTo-Json -Depth 6
```

### Test Bob app via proxy

```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/self-info" `
  -Method GET `
  -Headers @{ Host = "bob.192.168.208.150.nip.io:8080" } | ConvertTo-Json -Depth 6
```

---

## 11. Test cookie / session via proxy

### Alice login via proxy

```powershell
$body = @{
  username = "alice"
  password = "123"
} | ConvertTo-Json

$r = Invoke-WebRequest -Uri "http://192.168.208.150:8080/login" `
  -Method POST `
  -Headers @{ Host = "alice.192.168.208.150.nip.io:8080" } `
  -ContentType "application/json" `
  -Body $body `
  -SessionVariable sProxyAlice

$r.Content
$r.Headers["Set-Cookie"]
```

### Check `/me` via proxy

```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/me" `
  -Method GET `
  -Headers @{ Host = "alice.192.168.208.150.nip.io:8080" } `
  -WebSession $sProxyAlice | ConvertTo-Json -Depth 6
```

### Logout via proxy

```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/logout" `
  -Method POST `
  -Headers @{ Host = "alice.192.168.208.150.nip.io:8080" } `
  -WebSession $sProxyAlice | ConvertTo-Json -Depth 6
```

---

## 12. Test round-robin

Round-robin should be tested separately if you want cleaner logs.

```powershell
1..8 | ForEach-Object {
  Invoke-RestMethod -Uri "http://192.168.208.150:8080/instance" `
    -Method GET `
    -Headers @{ Host = "rr.local" } | ConvertTo-Json -Compress
}
```

Expected:
- requests alternate between the two configured instances

---

## 13. Final PASS checklist
- tracker starts successfully
- Alice and Bob register correctly
- tracker `/get-list` shows current dynamic IPs
- login / `/me` / logout pass
- direct API pass
- broadcast API pass
- UI refresh peers pass
- UI direct message pass
- UI broadcast pass
- proxy routing pass
- proxy dynamic peer resolution pass
- cookie/session through proxy pass
- round-robin pass if included in demo

---

## 14. Common issues

### Alice/Bob not shown on tracker
- forgot to call `/submit-info`
- registered wrong IP
- peer changed Wi-Fi/LAN but did not register again

### UI does not show peers
- `TRACKER_BASE` is not `http://192.168.208.150:9000`
- tracker is not running
- tracker has no registered peer yet

### `messages` returns unauthorized
- not logged in
- session cookie expired
- calling `/messages` without a valid cookie

### Proxy opens page but chat fails
- peer was not registered to tracker
- hostname does not match registered username
- proxy inferred HTTP port incorrectly from P2P port
- tracker route itself is wrong

### WinError 10049
- invalid bind IP
- the IP does not exist on the current network interface

### Proxy still points to old behavior
- `start_proxy.py` is still importing old `proxy.py`
- replace old proxy file or update import to use the dynamic tracker-based proxy

---

## 15. Demo notes
- prefer private/incognito windows to avoid stale cookies
- if Wi-Fi/LAN changes:
  - get new local IP again
  - restart peer
  - register peer again
- if using proxy dynamic mode:
  - tracker route must still be valid
  - peer usernames in URL must match tracker registration
