from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import engine
from app.lib.errors import register_error_handlers
from app.lib.logger import get_logger
from app.routes import admin, health, jobs, members, unsubscribe, webhooks

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"starting foodtech-hub (env={settings.app_env})")
    yield
    logger.info("shutting down, disposing db engine")
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="FoodTech Hub", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(admin.router)
    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(members.router)
    app.include_router(unsubscribe.router)
    app.include_router(webhooks.router)
    return app


app = create_app()
