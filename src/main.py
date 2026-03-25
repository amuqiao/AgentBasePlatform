import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.common.exceptions import AppException, app_exception_handler, generic_exception_handler
from src.common.middleware.request_context import RequestContextMiddleware
from src.config import get_settings

from src.auth.router import router as auth_router
from src.agent.router import router as agent_router
from src.conversation.router import router as conversation_router
from src.gateway.openai_router import router as openai_router

settings = get_settings()
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="智能体平台后端 API - MVP",
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_parameters={"persistAuthorization": True},
    )

    app.state.debug = settings.DEBUG

    # --- Middleware (order matters: last added = first executed) ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    # --- Exception handlers ---
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # --- Routers ---
    app.include_router(auth_router)
    app.include_router(agent_router)
    app.include_router(conversation_router)
    app.include_router(openai_router)

    @app.on_event("startup")
    async def log_api_docs_url():
        host = os.getenv("APP_HOST", "127.0.0.1")
        port = os.getenv("APP_PORT", "8000")
        display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        if app.docs_url:
            logger.info("Swagger UI docs: http://%s:%s%s", display_host, port, app.docs_url)
        if app.redoc_url:
            logger.info("ReDoc docs: http://%s:%s%s", display_host, port, app.redoc_url)

    # --- Health check ---
    @app.get("/health", tags=["系统"])
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/ready", tags=["系统"])
    async def ready():
        from src.common.database import engine
        from src.common.redis import redis_client

        checks = {}
        try:
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"

        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"

        all_ok = all(v == "ok" for v in checks.values())
        return {"status": "ok" if all_ok else "degraded", "checks": checks}

    return app


app = create_app()
