"""Rebookly API entry point.

Run from the backend folder:  uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.ai.client import AIClient
from app.ai.observability import LangfuseTracer, record_usage_in_database
from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser, SupabaseTokenVerifier
from app.clock import init_clock
from app.config import get_settings
from app.geo.geocoding import Geocoder
from app.jobs.scheduler import JobRunner, start_scheduler
from app.media.storage import SupabaseStorage
from app.payments.paypal import PayPalClient
from app.security.phone import PhoneProtector


logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("rebookly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts (before yield) and once when it stops (after yield)."""
    settings = get_settings()

    # ---------- Time ----------
    # Real clock in production, fast-forwardable clock in development.
    init_clock(simulated=settings.simulated_clock)

    # ---------- Database (Supabase Postgres) ----------
    database_url = settings.database_url.get_secret_value()
    if database_url:
        db.init_db(database_url)
    else:
        logger.warning("DATABASE_URL is missing: database features are disabled.")

    # ---------- Sign-in (verifies Supabase login tokens) ----------
    app.state.auth = None
    if settings.supabase_url:
        app.state.auth = SupabaseTokenVerifier(
            settings.supabase_url,
            legacy_jwt_secret=settings.supabase_jwt_secret.get_secret_value() or None,
        )
    else:
        logger.warning("SUPABASE_URL is missing: sign-in is disabled.")

    # ---------- Phone number protection (hashing and encryption) ----------
    app.state.phones = None
    encryption_keys = settings.data_encryption_key.get_secret_value()
    hash_key = settings.phone_hash_key.get_secret_value()
    if encryption_keys and hash_key:
        app.state.phones = PhoneProtector(encryption_keys, hash_key)
    else:
        logger.warning("DATA_ENCRYPTION_KEY or PHONE_HASH_KEY is missing: client sign-up is disabled.")

    # ---------- Photo storage (Supabase Storage, used only by the backend) ----------
    app.state.storage = None
    service_key = settings.supabase_service_role_key.get_secret_value()
    if settings.supabase_url and service_key:
        app.state.storage = SupabaseStorage(settings.supabase_url, service_key)
    else:
        logger.warning("Supabase storage is not configured: photo uploads are disabled.")

    # ---------- Location lookups (geocoder) ----------
    app.state.geocoder = None
    if settings.geocoder_base_url:
        app.state.geocoder = Geocoder(
            settings.geocoder_base_url,
            user_agent=settings.geocoder_user_agent,
            api_key=settings.geocoder_api_key.get_secret_value(),
            min_interval_seconds=settings.geocoder_min_interval_seconds,
        )
    else:
        logger.warning("GEOCODER_BASE_URL is missing: live location and address search are disabled.")

    # ---------- PayPal (one shared client for all requests) ----------
    app.state.paypal = None
    if settings.paypal_configured:
        app.state.paypal = PayPalClient(
            client_id=settings.paypal_client_id,
            client_secret=settings.paypal_client_secret.get_secret_value(),
            base_url=settings.paypal_api_base,
        )
    else:
        logger.warning("PayPal credentials are missing: payment features are disabled.")

    # ---------- AI (OpenAI, traced in Langfuse and recorded in ai_usage) ----------
    app.state.ai = None
    llm_key = settings.llm_api_key.get_secret_value()
    if llm_key and settings.llm_model:
        tracer = None
        langfuse_secret = settings.langfuse_secret_key.get_secret_value()
        if settings.langfuse_public_key and langfuse_secret:
            tracer = LangfuseTracer(
                settings.langfuse_public_key, langfuse_secret, settings.langfuse_base_url,
                capture_content=settings.langfuse_capture_content, environment=settings.app_env,
            )
        else:
            logger.warning("Langfuse keys are missing: AI calls won't be traced.")
        app.state.ai = AIClient(
            api_key=llm_key, model_smart=settings.llm_model, model_fast=settings.llm_model_fast,
            timeout_seconds=settings.ai_timeout_seconds, tracer=tracer, record_usage=record_usage_in_database,
            max_output_tokens=settings.ai_max_output_tokens,
        )
    else:
        logger.warning("LLM_API_KEY or LLM_MODEL is missing: AI features are disabled.")

    # ---------- Background jobs (release unpaid bookings, recover stuck payments) ----------
    # Started last, because jobs use the database and PayPal set up above.
    app.state.jobs, scheduler = None, None
    if settings.enable_jobs and db.is_db_ready():
        app.state.jobs = JobRunner(app.state.paypal)
        scheduler = start_scheduler(app.state.jobs)
    else:
        logger.warning("Background jobs are off.")

    logger.info(
        "Rebookly API started: env=%s, paypal=%s, database=%s, sign_in=%s, phone_protection=%s, "
        "storage=%s, geocoder=%s, ai=%s, jobs=%s, simulated_clock=%s, dev_routes=%s",
        settings.app_env, settings.paypal_env, db.is_db_ready(), app.state.auth is not None,
        app.state.phones is not None, app.state.storage is not None, app.state.geocoder is not None,
        app.state.ai is not None, app.state.jobs is not None, settings.simulated_clock, settings.enable_dev_routes,
    )

    yield

    # ---------- Shutdown: stop jobs first, then close connections ----------
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    if app.state.ai is not None:
        await app.state.ai.close()          # also sends any queued Langfuse traces
    if app.state.geocoder is not None:
        await app.state.geocoder.close()
    if app.state.storage is not None:
        await app.state.storage.close()
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
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ---------- System ----------
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

    # ---------- Public API (no sign-in, except address lookups) ----------
    from app.routers.public import businesses as public_businesses
    from app.routers.public import compliance as public_compliance
    from app.routers.public import documents as public_documents
    from app.routers.public import geo as public_geo
    from app.routers.public import search as public_search
    for module in (public_businesses, public_compliance, public_documents, public_geo,public_search):
        app.include_router(module.router)

    # ---------- Checkout (signed links, no sign-in) ----------
    from app.routers import checkout
    app.include_router(checkout.router)

    # ---------- Client API (signed-in clients) ----------
    from app.routers.client import bookings as client_bookings
    app.include_router(client_bookings.router)

    # ---------- Owner API (signed-in business owners) ----------
    from app.routers.owner import bookings as owner_bookings
    from app.routers.owner import businesses as owner_businesses
    from app.routers.owner import compliance as owner_compliance
    from app.routers.owner import dashboard as owner_dashboard
    from app.routers.owner import decisions as owner_decisions
    from app.routers.owner import location as owner_location
    from app.routers.owner import photos as owner_photos
    from app.routers.owner import policies as owner_policies
    from app.routers.owner import schedule as owner_schedule
    from app.routers.owner import services as owner_services
    from app.routers.owner import onboarding as owner_onboarding
    from app.routers.owner import team as owner_team
    for module in (
        # Setting up the business
        owner_businesses, owner_location, owner_compliance, owner_services, owner_policies,
        owner_schedule, owner_team, owner_photos, owner_onboarding,
        # Running it day to day
        owner_bookings, owner_decisions, owner_dashboard,
    ):
        app.include_router(module.router)

    # ---------- Development only (sandbox page, demo clock, AI ping). Never in production. ----------
    if settings.enable_dev_routes:
        from app.routers import dev
        app.include_router(dev.router)

    return app


app = create_app()