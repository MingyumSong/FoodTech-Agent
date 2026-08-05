from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import engine
from app.lib.errors import register_error_handlers
from app.lib.logger import get_logger
from app.routes import admin, health, jobs, members, reactions, unsubscribe, webhooks

STATIC_DIR = Path(__file__).parent / "static"

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
    app.include_router(reactions.router)
    app.include_router(unsubscribe.router)
    app.include_router(webhooks.router)
    # 뉴스레터 헤더 아이콘 등 이메일이 절대 URL로 불러가는 이미지 (T-013)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # admin.foodtech-center.org를 주소창에 치면 "/"로 들어온다. 라우트가 없어서
    # {"detail":"Not Found"}만 뜨던 걸 현황판으로 보낸다 (2026-08-06).
    # 이 앱엔 공개 페이지가 없다 — 관리자 화면·잡·웹훅뿐이라 첫 화면은 현황판이 맞다.
    @app.get("/", include_in_schema=False)
    @app.get("/admin", include_in_schema=False)
    def _home() -> RedirectResponse:
        return RedirectResponse("/admin/status")

    return app


app = create_app()
