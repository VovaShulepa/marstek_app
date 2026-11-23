"""Async UDP JSON-RPC client for Marstek Venus E Open API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class MarstekUdpClient:
    """Sends JSON-RPC requests over UDP and awaits a single response datagram."""

    def __init__(self, host: str, port: int = 30000, timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._req_id = 0
        self._pace = asyncio.Lock()
        self._not_before = 0.0

    def update_endpoint(self, host: str, port: int | None = None) -> None:
        self.host = host
        if port is not None:
            self.port = port

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        payload = {
            "id": self._next_id(),
            "method": method,
            "params": {"id": 0} if params is None else params,
        }
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        # Venus Wi-Fi drops the next packet when two queries land within a few seconds.
        async with self._pace:
            delay = self._not_before - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            loop = asyncio.get_running_loop()
            transport = None
            protocol: _UdpProtocol | None = None
            try:
                transport, protocol = await loop.create_datagram_endpoint(
                    lambda: _UdpProtocol(),
                    remote_addr=(self.host, self.port),
                )
                assert protocol is not None
                started = time.perf_counter()
                transport.sendto(data)
                raw = await asyncio.wait_for(protocol.wait_response(), timeout=timeout or self.timeout)
                latency_ms = int((time.perf_counter() - started) * 1000)
                response = json.loads(raw.decode("utf-8"))
                response["_latency_ms"] = latency_ms
                return response
            except Exception as exc:
                logger.debug("UDP call %s failed: %s", method, exc)
                raise
            finally:
                self._not_before = time.monotonic() + 3.6
                if transport is not None:
                    transport.close()

    async def get_device(self) -> dict[str, Any]:
        return await self.call("Marstek.GetDevice", {"ble_mac": "0"})

    async def get_wifi_status(self) -> dict[str, Any]:
        return await self.call("Wifi.GetStatus", {"id": 0})

    async def get_ble_status(self) -> dict[str, Any]:
        return await self.call("BLE.GetStatus", {"id": 0})

    async def get_battery_status(self) -> dict[str, Any]:
        return await self.call("Bat.GetStatus", {"id": 0})

    async def get_es_status(self) -> dict[str, Any]:
        return await self.call("ES.GetStatus", {"id": 0}, timeout=1.5)

    async def get_es_mode(self) -> dict[str, Any]:
        return await self.call("ES.GetMode", {"id": 0})

    async def get_em_status(self) -> dict[str, Any]:
        return await self.call("EM.GetStatus", {"id": 0})

    async def set_es_mode(self, config: dict[str, Any]) -> dict[str, Any]:
        return await self.call("ES.SetMode", {"id": 0, "config": config})

    async def set_dod(self, value: int) -> dict[str, Any]:
        return await self.call("DOD.SET", {"value": value})

    async def set_led(self, on: bool) -> dict[str, Any]:
        return await self.call("Led.Ctrl", {"state": 1 if on else 0})

    async def set_ble_broadcast(self, enabled: bool) -> dict[str, Any]:
        # enable 0 keeps advertising, enable 1 blocks it.
        return await self.call("Ble.Adv", {"enable": 0 if enabled else 1})

    async def set_power_version(self, watts: int) -> dict[str, Any]:
        return await self.call("Set.Ver", {"version": watts})


class _UdpProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self._future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:  # noqa: ARG002
        if not self._future.done():
            self._future.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if not self._future.done():
            self._future.set_exception(exc)

    def connection_lost(self, exc: Exception | None) -> None:
        if exc and not self._future.done():
            self._future.set_exception(exc)

    async def wait_response(self) -> bytes:
        return await self._future


def _normalize_ip(ip: Any) -> str:
    if not isinstance(ip, str):
        return ""
    parts = ip.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        return ".".join(str(int(part)) for part in parts)
    return ip


def _broadcast_addresses() -> list[str]:
    import re
    import subprocess

    found: list[str] = []
    for cmd in (["ifconfig"], ["ip", "-4", "-o", "addr", "show"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        found.extend(re.findall(r"\b(?:broadcast|brd)\s+(\d{1,3}(?:\.\d{1,3}){3})", out))
        if found:
            break
    return list(dict.fromkeys(found))


def _discover_sync(port: int, timeout: float) -> list[dict[str, Any]]:
    import socket

    payload = json.dumps(
        {"id": 0, "method": "Marstek.GetDevice", "params": {"ble_mac": "0"}},
        separators=(",", ":"),
    ).encode("utf-8")
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sent = 0
        last_error: Exception | None = None
        for addr in _broadcast_addresses() + ["255.255.255.255"]:
            try:
                sock.sendto(payload, (addr, port))
                sent += 1
            except OSError as exc:
                last_error = exc
        if not sent and last_error is not None:
            raise last_error

        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                sock.settimeout(remaining)
                data, addr = sock.recvfrom(4096)
            except TimeoutError:
                break
            except socket.timeout:
                break
            try:
                response = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            result = response.get("result") or {}
            if not isinstance(result, dict) or not result.get("device"):
                continue
            key = str(result.get("wifi_mac") or result.get("ble_mac") or addr[0])
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "model": result.get("device") or "",
                    "firmware": result.get("ver"),
                    "ip": addr[0] or _normalize_ip(result.get("ip")),
                    "wifi_mac": result.get("wifi_mac") or "",
                    "ssid": result.get("wifi_name") or "",
                }
            )
    return found


async def discover_devices(port: int = 30000, timeout: float = 2.5) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_discover_sync, port, timeout)
