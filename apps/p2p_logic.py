from __future__ import annotations

import asyncio
import contextlib
import json
import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional


ALL_MESSAGES_CHANNEL = "__all__"


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

    def _build_dm_channel(self, user_a: str, user_b: str) -> str:
        left = str(user_a or "").strip()
        right = str(user_b or "").strip()
        return f"dm:{':'.join(sorted([left, right]))}"

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
                if msg_type not in {"direct", "broadcast"}:
                    print(f"[P2P] skip unsupported message type: {msg_type}")
                    continue

                self._store_message(payload, direction="in")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

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

            msg_type = payload.get("type", "direct")
            sender = payload.get("from", "unknown")
            receiver = payload.get("to")
            channel = payload.get("channel", "general")

            if msg_type == "direct":
                channel = self._build_dm_channel(sender, receiver)

            msg = {
                "seq": self._next_seq_unlocked(),
                "id": msg_id,
                "type": msg_type,
                "channel": channel,
                "from": sender,
                "to": receiver,
                "text": payload.get("text", ""),
                "ts": payload.get("ts", int(time.time())),
                "direction": direction,
            }
            print(
                f"[P2P] store message channel={channel} "
                f"type={msg_type} from={msg['from']} to={msg.get('to')} "
                f"text={msg['text']} direction={direction}"
            )
            self._messages[channel].append(msg)
            return msg

    def get_messages(self, channel: str = ALL_MESSAGES_CHANNEL, after_seq: int = 0) -> Dict[str, Any]:
        with self._lock:
            if channel == ALL_MESSAGES_CHANNEL:
                all_msgs: List[Dict[str, Any]] = []
                for bucket in self._messages.values():
                    all_msgs.extend(bucket)
                all_msgs.sort(key=lambda item: item["seq"])
                new_msgs = [m for m in all_msgs if m["seq"] > int(after_seq)]
                last_seq = all_msgs[-1]["seq"] if all_msgs else 0
            else:
                all_msgs = list(self._messages.get(channel, []))
                new_msgs = [m for m in all_msgs if m["seq"] > int(after_seq)]
                last_seq = all_msgs[-1]["seq"] if all_msgs else 0

        return {
            "ok": True,
            "channel": channel,
            "messages": new_msgs,
            "last_seq": last_seq,
        }

    async def _send_json(self, ip: str, port: int, payload: Dict[str, Any]) -> None:
        reader, writer = await asyncio.open_connection(ip, int(port))

        raw = json.dumps(payload) + "\n"
        print(f"[P2P] raw send -> {raw.strip()}")
        writer.write(raw.encode("utf-8"))

        await writer.drain()
        writer.close()
        await writer.wait_closed()

    def send_direct_sync(
        self,
        sender: str,
        to: str,
        ip: str,
        port: int,
        channel: str,
        text: str,
    ) -> Dict[str, Any]:
        dm_channel = channel or self._build_dm_channel(sender, to)

        payload = {
            "id": str(uuid.uuid4()),
            "type": "direct",
            "from": sender,
            "to": to,
            "channel": dm_channel,
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
            return {
                "ok": True,
                "message": "sent",
                "id": payload["id"],
                "channel": dm_channel,
                "to": to,
            }
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
            return {"ok": True, "results": results, "id": payload["id"]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}