from __future__ import annotations

import asyncio
import contextlib
import json
import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional


class P2PNode:
    def __init__(self, listen_host: str = "0.0.0.0", listen_port: int = 9101) -> None:
        self.listen_host = listen_host
        self.listen_port = int(listen_port)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._ready = threading.Event()

        self._lock = threading.Lock()
        self._messages: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._seen_ids: set[str] = set()
        self._seq = 0

    # -------------------------
    # lifecycle
    # -------------------------
    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        if not self._ready.wait(timeout=3):
            raise RuntimeError("P2P node failed to start")

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start_server())
        self._ready.set()
        self._loop.run_forever()

    async def _start_server(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_peer_connection,
            self.listen_host,
            self.listen_port,
        )
        print(f"[P2P] listening on {self.listen_host}:{self.listen_port}")

    def _require_loop(self) -> asyncio.AbstractEventLoop:
        if not self._loop:
            raise RuntimeError("P2P event loop not running")
        return self._loop

    # -------------------------
    # incoming
    # -------------------------
    async def _handle_peer_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        print(f"[P2P] incoming connection from {peer}")

        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break

                try:
                    payload = json.loads(raw.decode("utf-8").strip())
                    print(f"[P2P] received payload: {payload}")
                except json.JSONDecodeError as exc:
                    print(f"[P2P] invalid json: {exc}; raw={raw!r}")
                    continue

                msg_type = payload.get("type")
                if msg_type not in {"chat", "broadcast"}:
                    print(f"[P2P] skip unsupported message type: {msg_type}")
                    continue

                self._store_message(payload, direction="in")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    # -------------------------
    # local storage
    # -------------------------
    def _next_seq_unlocked(self) -> int:
        self._seq += 1
        return self._seq

    def _store_message(self, payload: Dict[str, Any], direction: str) -> Optional[Dict[str, Any]]:
        msg_id = payload.get("id")
        if not msg_id:
            return None

        with self._lock:
            if msg_id in self._seen_ids:
                return None
            self._seen_ids.add(msg_id)

            channel = payload.get("channel", "general")
            msg = {
                "seq": self._next_seq_unlocked(),
                "id": msg_id,
                "type": payload.get("type", "chat"),
                "channel": channel,
                "from": payload.get("from", "unknown"),
                "text": payload.get("text", ""),
                "ts": payload.get("ts", int(time.time())),
                "direction": direction,
            }
            print(
                f"[P2P] store message channel={channel} "
                f"from={msg['from']} text={msg['text']} direction={direction}"
            )
            self._messages[channel].append(msg)
            return msg

    def get_messages(self, channel: str = "general", after_seq: int = 0) -> Dict[str, Any]:
        with self._lock:
            all_msgs = list(self._messages.get(channel, []))
            new_msgs = [m for m in all_msgs if m["seq"] > int(after_seq)]
            last_seq = all_msgs[-1]["seq"] if all_msgs else 0

        return {
            "ok": True,
            "channel": channel,
            "messages": new_msgs,
            "last_seq": last_seq,
        }

    # -------------------------
    # outgoing
    # -------------------------
    async def _send_json(self, ip: str, port: int, payload: Dict[str, Any]) -> None:
        reader, writer = await asyncio.open_connection(ip, int(port))

        # IMPORTANT: must be a real newline, not "\\n"
        raw = json.dumps(payload) + "\n"
        print(f"[P2P] raw send -> {raw.strip()}")
        writer.write(raw.encode("utf-8"))

        await writer.drain()
        writer.close()
        await writer.wait_closed()

    def send_direct_sync(
        self,
        sender: str,
        ip: str,
        port: int,
        channel: str,
        text: str,
    ) -> Dict[str, Any]:
        payload = {
            "id": str(uuid.uuid4()),
            "type": "chat",
            "from": sender,
            "channel": channel or "general",
            "text": text,
            "ts": int(time.time()),
        }

        print(f"[P2P] send direct -> {ip}:{port} payload={payload}")

        fut = asyncio.run_coroutine_threadsafe(
            self._send_json(ip, int(port), payload),
            self._require_loop(),
        )

        try:
            fut.result(timeout=5)
            self._store_message(payload, direction="out")
            return {"ok": True, "message": "sent"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _broadcast_many(
        self,
        peers: List[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        async def _send_one(peer: Dict[str, Any]) -> Dict[str, Any]:
            ip = peer.get("ip")
            port = int(peer.get("port", 0))
            username = peer.get("username", "unknown")

            if not ip or not port:
                return {"peer": username, "ok": False, "error": "missing ip/port"}

            if port == self.listen_port and ip in {"127.0.0.1", "localhost", self.listen_host}:
                return {"peer": username, "ok": True, "skipped": True}

            try:
                await self._send_json(ip, port, payload)
                return {"peer": username, "ok": True}
            except Exception as exc:
                return {"peer": username, "ok": False, "error": str(exc)}

        return await asyncio.gather(*[_send_one(peer) for peer in peers])

    def broadcast_sync(
        self,
        sender: str,
        peers: List[Dict[str, Any]],
        channel: str,
        text: str,
    ) -> Dict[str, Any]:
        payload = {
            "id": str(uuid.uuid4()),
            "type": "broadcast",
            "from": sender,
            "channel": channel or "general",
            "text": text,
            "ts": int(time.time()),
        }

        print(f"[P2P] broadcast -> peers={peers} payload={payload}")

        fut = asyncio.run_coroutine_threadsafe(
            self._broadcast_many(peers, payload),
            self._require_loop(),
        )

        try:
            results = fut.result(timeout=8)
            self._store_message(payload, direction="out")
            return {"ok": True, "results": results}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}