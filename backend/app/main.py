from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.database import create_pool
from app.core.runtime_cache import RuntimeCache


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or get_settings()

    @asynccontextmanager
    async def lifespan(instance: FastAPI):
        pool = create_pool(configuration)
        instance.state.database_pool = pool
        if pool is not None:
            pool.open()
        try:
            yield
        finally:
            if pool is not None:
                pool.close()
            instance.state.database_pool = None

    application = FastAPI(
        lifespan=lifespan,
        title="AeroRoute API",
        version=configuration.app_version,
        description="Walking candidates and station-interpolated PM2.5 exposure with data quality.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configuration.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "aeroroute-api",
            "version": configuration.app_version,
            "environment": configuration.environment,
        }

    application.state.database_pool = None
    application.state.snapshot_cache = RuntimeCache()
    application.state.route_cache = RuntimeCache()
    application.state.settings = configuration
    application.include_router(router)
    return application


app = create_app()
