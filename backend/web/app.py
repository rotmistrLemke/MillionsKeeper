"""
web/app.py — FastAPI v2 приложение MillionsKeeper.

Эндпоинты:
  /api/*      — REST (см. app/api/routes.py)
  /ws/events  — WebSocket realtime
  /           — React SPA (frontend/dist/index.html в prod)

Запуск:
  uvicorn web.app:app --host 0.0.0.0 --port 8080 --reload
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.websocket import handle_ws_session, ws_event_bridge
from app.cache.market_cache import init_cache
from app.core.config import settings

logger = logging.getLogger("WebApp")

app = FastAPI(
    title="MillionsKeeper v2",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST роутер ───────────────────────────────────────────────────────────────

app.include_router(api_router)

# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket) -> None:
    await handle_ws_session(ws)

# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    # Redis кэш
    await init_cache(settings.redis_url, settings.enable_redis_cache)

    # Подписываем WS bridge на все события шины
    try:
        from core.event_bus import bus
        bus.subscribe("*", ws_event_bridge)
        logger.info("WS bridge подписан на EventBus")
    except Exception as e:
        logger.warning(f"EventBus недоступен: {e}")

    logger.info(f"MillionsKeeper v2 запущен на http://{settings.web_host}:{settings.web_port}")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    try:
        from app.cache.market_cache import get_cache
        await get_cache().close()
    except Exception:
        pass

# ── Static / SPA ──────────────────────────────────────────────────────────────

_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if _DIST.exists():
    # Prod: отдаём сбилженный React
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # Не перехватываем /api и /ws
        if full_path.startswith("api") or full_path.startswith("ws"):
            from fastapi import Response
            return Response(status_code=404)
        index = _DIST / "index.html"
        return FileResponse(str(index))
else:
    # Dev: Vite dev server на :3000, здесь отдаём только API
    @app.get("/", include_in_schema=False)
    async def dev_root() -> dict:
        return {
            "message": "MillionsKeeper v2 backend",
            "docs":    "/api/docs",
            "frontend": "http://localhost:3000 (npm run dev)",
        }
