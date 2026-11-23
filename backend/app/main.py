"""FastAPI entrypoint: REST + WebSocket bridge for Marstek Venus E."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .models import (
    ApiResponse,
    DeviceControl,
    HealthResponse,
    ManualSlot,
    ModeUpdate,
    ReserveSession,
    SelfDrawInfo,
    SimulatorOverride,
    StationConfigUpdate,
)
from .station import StationService
from .udp_client import discover_devices
from .ws_manager import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("marstek")

settings = get_settings()
station = StationService(settings)
manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await station.start()
    broadcaster = asyncio.create_task(_broadcast_loop())
    logger.info(
        "Marstek bridge started (demo=%s, ip=%s:%s)",
        settings.demo_mode,
        settings.marstek_ip,
        settings.marstek_port,
    )
    yield
    broadcaster.cancel()
    await station.stop()


app = FastAPI(title="Marstek Venus E Bridge", version="1.0.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _broadcast_loop() -> None:
    while True:
        try:
            state = station.get_state()
            await manager.broadcast(state.model_dump())
        except Exception as exc:
            logger.debug("Broadcast error: %s", exc)
        await asyncio.sleep(settings.poll_interval_seconds)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    s = station.get_state()
    return HealthResponse(demo_mode=s.demo_mode, connected=s.connected)


@app.get("/api/state")
async def get_state():
    return station.get_state()


@app.post("/api/mode", response_model=ApiResponse)
async def post_mode(body: ModeUpdate) -> ApiResponse:
    ok, message, state = await station.set_mode(body)
    await manager.broadcast(state.model_dump())
    return ApiResponse(ok=ok, message=message, state=state)


@app.post("/api/schedule", response_model=ApiResponse)
async def post_schedule(body: ManualSlot) -> ApiResponse:
    ok, message, state = await station.apply_schedule(body)
    await manager.broadcast(state.model_dump())
    return ApiResponse(ok=ok, message=message, state=state)


@app.post("/api/device", response_model=ApiResponse)
async def post_device(body: DeviceControl) -> ApiResponse:
    ok, message, state = await station.apply_device(body)
    await manager.broadcast(state.model_dump())
    return ApiResponse(ok=ok, message=message, state=state)


@app.get("/api/discover")
async def get_discover():
    try:
        devices = await discover_devices(station.settings.marstek_port)
    except Exception as exc:
        logger.warning("Discovery failed: %s", exc)
        return {"ok": False, "message": "Пошук у мережі не вдався", "devices": []}
    if not devices:
        return {
            "ok": True,
            "message": "Станцій не видно. Увімкни Local API в додатку Marstek і перевір ту саму Wi‑Fi мережу.",
            "devices": [],
        }
    return {"ok": True, "message": f"Знайдено: {len(devices)}", "devices": devices}


@app.post("/api/events/clear", response_model=ApiResponse)
async def clear_events() -> ApiResponse:
    state = await station.clear_events()
    await manager.broadcast(state.model_dump())
    return ApiResponse(ok=True, message="Журнал очищено", state=state)


@app.get("/api/sessions", response_model=list[ReserveSession])
async def get_sessions() -> list[ReserveSession]:
    return await station.list_sessions()


@app.get("/api/telemetry")
async def get_telemetry(hours: float = 24.0):
    hours = max(0.25, min(336.0, hours))
    rows = await station.list_telemetry(hours=hours)
    return {"hours": hours, "count": len(rows), "samples": [row.model_dump() for row in rows]}


@app.get("/api/self-draw", response_model=SelfDrawInfo)
async def get_self_draw() -> SelfDrawInfo:
    return await station.self_draw_report()


@app.post("/api/sessions/clear", response_model=ApiResponse)
async def clear_sessions() -> ApiResponse:
    state = await station.clear_sessions()
    await manager.broadcast(state.model_dump())
    return ApiResponse(ok=True, message="Облік очищено", state=state)


@app.post("/api/config", response_model=ApiResponse)
async def post_config(body: StationConfigUpdate) -> ApiResponse:
    state = await station.update_config(body)
    await manager.broadcast(state.model_dump())
    return ApiResponse(ok=True, message="Конфігурацію збережено", state=state)


@app.post("/api/simulator", response_model=ApiResponse)
async def post_simulator(body: SimulatorOverride) -> ApiResponse:
    if not settings.demo_mode and not station.settings.demo_mode:
        return ApiResponse(ok=False, message="Симулятор доступний лише в DEMO режимі")
    state = await station.apply_simulator(body)
    await manager.broadcast(state.model_dump())
    return ApiResponse(ok=True, message="Симулятор оновлено", state=state)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        # Send current snapshot immediately
        await websocket.send_json(station.get_state().model_dump())
        while True:
            # Keep alive / allow client pings
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)


# Optional: serve built frontend from ../frontend/dist
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")


def run() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
