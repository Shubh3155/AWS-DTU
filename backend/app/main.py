from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or get_settings()
    application = FastAPI(
        title="AeroRoute API",
        version=configuration.app_version,
        description="Walking-route PM2.5 exposure comparison. Initial setup; scoring is pending.",
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

    application.include_router(router)
    return application


app = create_app()
