"""Rebookly API entry point.

Run from the backend folder:  uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clock import init_clock
from app.config import get_settings
from app.payments.paypal import PayPalClient
from app import db

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("rebookly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts (before yield) and once when it stops (after yield)."""
    settings = get_settings()

    init_clock(simulated=settings.simulated_clock)

    database_url = settings.database_url.get_secret_value()
    if database_url:
        db.init_db(database_url)
    else:
        logger.warning("DATABASE_URL is missing: database features are disabled.")

    app.state.paypal = None
    if settings.paypal_configured:
        app.state.paypal = PayPalClient(
            client_id=settings.paypal_client_id,
            client_secret=settings.paypal_client_secret.get_secret_value(),
            base_url=settings.paypal_api_base,
        )
    else:
        logger.warning("PayPal credentials are missing: payment features are disabled.")

    logger.info(
        "Rebookly API started: env=%s, paypal=%s, database=%s, simulated_clock=%s, dev_routes=%s",
        settings.app_env, settings.paypal_env, db.is_db_ready(),
        settings.simulated_clock, settings.enable_dev_routes,
    )
    yield

    if app.state.paypal is not None:
        await app.state.paypal.close()
    await db.close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    is_production = settings.app_env == "production"

    app = FastAPI(
        title="Rebookly API",
        version="0.1.0",
        lifespan=lifespan,
        # Interactive API docs are handy in development but not exposed in production.
        docs_url=None if is_production else "/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/openapi.json",
    )

    # Only our own Flutter web app may call this API from a browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health", tags=["system"])
    async def health():
        database = "not configured"
        if db.is_db_ready():
            try:
                await db.check_db()
                database = "ok"
            except Exception:
                logger.exception("Database health check failed")
                database = "unavailable"
        return {
            "status": "ok" if database != "unavailable" else "degraded",
            "app_env": settings.app_env,
            "paypal_env": settings.paypal_env,
            "paypal_configured": settings.paypal_configured,
            "database": database,
        }


app = create_app()