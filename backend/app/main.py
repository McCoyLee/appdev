from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .api import actions, branches, chat, logs_stream, preview, probe, projects, prs, repo, secrets, templates
from .core.config import get_settings
from .core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("App start | env={} | port={}", settings.app_env, settings.app_port)
    yield
    logger.info("App shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="App For Oneself",
        description="AI 造应用：用户带 GitHub + AI Key，浏览器里造应用",
        version="0.0.1",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz():
        return {
            "status": "ok",
            "env": settings.app_env,
            "deepseek_configured": bool(settings.deepseek_api_key),
            "github_configured": bool(settings.github_token),
        }

    app.include_router(repo.router)
    app.include_router(secrets.router)
    app.include_router(actions.router)
    app.include_router(preview.router)
    app.include_router(branches.router)
    app.include_router(prs.router)
    app.include_router(templates.router)
    app.include_router(projects.router)
    app.include_router(probe.router)
    app.include_router(logs_stream.router)
    app.include_router(chat.router)
    return app


app = create_app()
