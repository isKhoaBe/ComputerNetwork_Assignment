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

## Before Running

### 1) Backend mode
This project uses:
- **coroutine mode** for the backend/web application layer
- **threading mode** for the proxy layer

### 2) `static/js/chat.js`
Make sure `TRACKER_BASE` points to the tracker machine:

```javascript
const TRACKER_BASE = "http://192.168.208.150:9000";
```

### 3) About proxy mode
This README assumes you are using the **dynamic tracker-based proxy** version of `proxy.py`.

That means:
- the tracker route is still static
- peer backends such as Alice/Bob are resolved dynamically from tracker `/get-list`
- if Alice/Bob changes Wi-Fi/LAN IP, you do **not** need to rewrite peer IPs in `proxy.conf`
- however, the peer must **restart and register again** with the tracker after its IP changes

### 4) About `proxy.conf`
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

### 5) Current proxy assumption
The dynamic proxy currently infers HTTP port from registered P2P port using:

- `9101 -> 9001`
- `9102 -> 9002`

So if you change the port convention, update proxy logic or store `http_port` in tracker.

---

# COMMAND ORDER – RUN IN THIS EXACT ORDER

## STEP 1 — Start tracker on tracker machine
Run this **only on the tracker machine**:

```powershell
$env:APP_MODE="tracker"
$env:APP_IP="192.168.208.150"
$env:P2P_PORT="9100"
$env:INSTANCE_ID="tracker"
py start_sampleapp.py --server-ip 192.168.208.150 --server-port 9000 --mode tracker
```

Keep this terminal open.

---

## STEP 2 — Check tracker is alive
Run on tracker machine or any machine that can reach tracker:

```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:9000/get-list" -Method GET | ConvertTo-Json -Depth 6
```

If this works, the tracker is ready.

---

## STEP 3 — Start Alice on Alice machine
Run this **only on Alice machine**.

### 3.1 Get Alice current IP
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

> If this prints `192.168.208.150`, you are on the tracker machine, not Alice machine.

### 3.2 Start Alice peer
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

Keep this terminal open.

### 3.3 Register Alice to tracker
Open a second terminal on Alice machine and run:

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

Invoke-RestMethod -Uri "http://${trackerIp}:9000/submit-info" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

---

## STEP 4 — Start Bob on Bob machine
Run this **only on Bob machine**.

### 4.1 Get Bob current IP
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

> If this prints `192.168.208.150`, you are on the tracker machine, not Bob machine.

### 4.2 Start Bob peer
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

Keep this terminal open.

### 4.3 Register Bob to tracker
Open a second terminal on Bob machine and run:

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

Invoke-RestMethod -Uri "http://${trackerIp}:9000/submit-info" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

---

## STEP 5 — Verify tracker list again
Run on tracker machine:

```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:9000/get-list" -Method GET | ConvertTo-Json -Depth 6
```

Expected:
- `alice` appears with Alice’s current IP
- `bob` appears with Bob’s current IP

---

## STEP 6 — Open UI directly first
Do this before testing proxy.

### On Alice machine
Open:
```text
http://<Alice_Current_IP>:9001/login.html
```

### On Bob machine
Open:
```text
http://<Bob_Current_IP>:9002/login.html
```

Login:
- Alice uses `alice / 123`
- Bob uses `bob / 123`

Then go to:
- `http://<Alice_Current_IP>:9001/index.html`
- `http://<Bob_Current_IP>:9002/index.html`

Check:
- click `Refresh Peers`
- Alice sees Bob
- Bob sees Alice

---

## STEP 7 — Test API direct message
### On Alice machine
Replace `<Bob_Current_IP>` and `<Alice_Current_IP>` first.

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

### On Bob machine
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

---

## STEP 8 — Test API broadcast
### On Alice machine
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

## STEP 9 — Start proxy
Run on tracker machine:

```powershell
py start_proxy.py --server-ip 192.168.208.150 --server-port 8080
```

Keep this terminal open.

---

## STEP 10 — Test proxy basic routing

### Tracker via proxy
```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/get-list" `
  -Method GET `
  -Headers @{ Host = "192.168.208.150:8080" } | ConvertTo-Json -Depth 6
```

### Alice via proxy
```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/self-info" `
  -Method GET `
  -Headers @{ Host = "alice.192.168.208.150.nip.io:8080" } | ConvertTo-Json -Depth 6
```

### Bob via proxy
```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/self-info" `
  -Method GET `
  -Headers @{ Host = "bob.192.168.208.150.nip.io:8080" } | ConvertTo-Json -Depth 6
```

---

## STEP 11 — Test login via proxy

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

### Check `/me`
```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/me" `
  -Method GET `
  -Headers @{ Host = "alice.192.168.208.150.nip.io:8080" } `
  -WebSession $sProxyAlice | ConvertTo-Json -Depth 6
```

### Logout
```powershell
Invoke-RestMethod -Uri "http://192.168.208.150:8080/logout" `
  -Method POST `
  -Headers @{ Host = "alice.192.168.208.150.nip.io:8080" } `
  -WebSession $sProxyAlice | ConvertTo-Json -Depth 6
```

---

## STEP 12 — Test round-robin (optional)
Run on tracker machine:

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

## Fast Checklist
- [ ] Tracker started
- [ ] Alice started
- [ ] Alice registered
- [ ] Bob started
- [ ] Bob registered
- [ ] `/get-list` shows Alice and Bob
- [ ] Alice login works
- [ ] Bob login works
- [ ] Direct API works
- [ ] Broadcast API works
- [ ] UI direct chat works
- [ ] UI broadcast works
- [ ] Proxy starts
- [ ] Proxy routes tracker correctly
- [ ] Proxy resolves Alice correctly
- [ ] Proxy resolves Bob correctly
- [ ] Proxy login/session works
- [ ] Round-robin works if included

---

## Common mistakes
- Running the “get dynamic IP” script on the tracker machine instead of Alice/Bob machine
- Forgetting to replace `TRACKER_BASE`
- Forgetting to register peer after start
- Using the wrong tracker IP
- Testing proxy with old `proxy.py` instead of dynamic tracker-based proxy
- Using stale browser cache after changing `chat.js`
