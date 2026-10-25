"""Rebookly API entry point.

Run from the backend folder:  uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser, SupabaseTokenVerifier
from app.clock import init_clock
from app.config import get_settings
from app.payments.paypal import PayPalClient
from app.security.phone import PhoneProtector
from app.media.storage import SupabaseStorage

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("rebookly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts (before yield) and once when it stops (after yield)."""
    settings = get_settings()

    # Time: real clock in production, fast-forwardable clock in development.
    init_clock(simulated=settings.simulated_clock)

    # Database (Supabase Postgres).
    database_url = settings.database_url.get_secret_value()
    if database_url:
        db.init_db(database_url)
    else:
        logger.warning("DATABASE_URL is missing: database features are disabled.")

    # Sign-in: verifies Supabase login tokens.
    app.state.auth = None
    if settings.supabase_url:
        app.state.auth = SupabaseTokenVerifier(
            settings.supabase_url,
            legacy_jwt_secret=settings.supabase_jwt_secret.get_secret_value() or None,
        )
    else:
        logger.warning("SUPABASE_URL is missing: sign-in is disabled.")

    # Phone number protection (hashing and encryption).
    app.state.phones = None
    encryption_keys = settings.data_encryption_key.get_secret_value()
    hash_key = settings.phone_hash_key.get_secret_value()
    if encryption_keys and hash_key:
        app.state.phones = PhoneProtector(encryption_keys, hash_key)
    else:
        logger.warning("DATA_ENCRYPTION_KEY or PHONE_HASH_KEY is missing: client sign-up is disabled.")

    # PayPal: one shared client for all requests.
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
        "Rebookly API started: env=%s, paypal=%s, database=%s, sign_in=%s, phone_protection=%s, "
        "simulated_clock=%s, dev_routes=%s",
        settings.app_env, settings.paypal_env, db.is_db_ready(), app.state.auth is not None,
        app.state.phones is not None, settings.simulated_clock, settings.enable_dev_routes,
    )
    yield

    # Shutdown: close connections cleanly.
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

    @app.get("/api/me", tags=["auth"])
    async def me(user: AuthUser = Depends(get_current_user)):
        """Who am I? Used by the app to confirm a sign-in works."""
        return {
            "user_id": str(user.id),
            "is_anonymous": user.is_anonymous,
            "signed_in_with": "phone" if user.phone else "email" if user.email else "other",
        }

    
        # Owner API
        # Owner API
        # Public API (no sign-in)
    from app.routers.public import businesses as public_businesses
    app.include_router(public_businesses.router)
    from app.routers.owner import businesses as owner_businesses
    from app.routers.owner import policies as owner_policies
    from app.routers.owner import services as owner_services
    from app.routers.owner import schedule as owner_schedule
    app.include_router(owner_schedule.router)
    app.include_router(owner_businesses.router)
    app.include_router(owner_services.router)
    app.include_router(owner_policies.router)
    # Client API and checkout
    from app.routers import checkout
    from app.routers.client import bookings as client_bookings
    app.include_router(client_bookings.router)
    app.include_router(checkout.router)
    from app.routers.owner import bookings as owner_bookings
    app.include_router(owner_bookings.router)


    # Development-only routes (sandbox test page, demo clock). Never enabled in production.
    if settings.enable_dev_routes:
        from app.routers import dev
        app.include_router(dev.router)

    return app


app = create_app()