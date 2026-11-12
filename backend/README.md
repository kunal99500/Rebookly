# Rebookly backend

The backend is a FastAPI application. It owns booking and scheduling rules, persists application data in PostgreSQL through SQLAlchemy, verifies client and owner identity tokens, and integrates with external services such as PayPal, Supabase Storage, email, geocoding, and AI providers.

## Requirements

- Python 3.10 or newer
- pip and Python virtual-environment support
- PostgreSQL for database-backed functionality (Supabase Postgres is used by this project)

The pinned dependencies are listed in `requirements.txt`. PostgreSQL connections use the asynchronous `asyncpg` driver and require SSL.

## Install

From the repository root, create a virtual environment and install dependencies:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

In Command Prompt, activate the environment with `.venv\Scripts\activate.bat` if desired. On macOS/Linux, use `python3 -m venv .venv`, `source .venv/bin/activate`, and `cp .env.example .env`.

Edit `backend/.env` with the integrations you want to use. It is intentionally ignored by Git; do not commit it or share its contents.

## Configuration

Settings are loaded from `backend/.env` or the process environment by `app.config.get_settings`. Environment variable names are case-insensitive. Empty values generally disable the associated integration.

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` or `production`. Production disables interactive API docs and requires data-protection keys. |
| `FRONTEND_URL` | Exact browser origin allowed by CORS. Local default: `http://localhost:5000`. |
| `BACKEND_URL` | Public base URL used when the backend constructs links. Local default: `http://localhost:8000`. |
| `DATABASE_URL` | PostgreSQL connection string. Use the Supabase connection string; credentials must be URL-encoded when they contain reserved URL characters. |
| `SUPABASE_URL` | Supabase project URL, used for authentication and storage. |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only key for Supabase Storage operations. Never expose it to the frontend. |
| `SUPABASE_JWT_SECRET` | Legacy HS256 token verification secret, only for projects still using legacy Supabase JWTs. |
| `FIREBASE_PROJECT_ID` | Firebase project ID for verifying client phone-auth tokens. |
| `DATA_ENCRYPTION_KEY` | Fernet key(s) used to encrypt stored phone numbers. Required in production. Multiple rotation keys may be comma-separated, newest first. |
| `PHONE_HASH_KEY` | Secret key used to produce lookup hashes for phone numbers. Required in production and must be at least 32 characters. |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | PayPal application credentials. |
| `PAYPAL_ENV` | `sandbox` or `live`; use `sandbox` during development. |
| `PAYPAL_WEBHOOK_ID` | PayPal webhook ID used when verifying webhook signatures. |
| `PAYPAL_PARTNER_MERCHANT_ID` | Rebookly's PayPal partner merchant account ID. |
| `PAYPAL_REQUIRE_CONNECTED_ACCOUNT` | Require businesses to connect a PayPal account before taking bookings. |
| `PAYPAL_PRO_PLAN_ID` | PayPal billing plan ID used for the Pro subscription. |
| `DEFAULT_CURRENCY` | Three-letter default currency code, for example `USD` or `INR`. |
| `PLATFORM_FEES_ENABLED` | Enables the platform-fee behavior when the PayPal setup supports it. |
| `PRO_PRICE_LABEL` | Display label for the Pro plan price. |
| `LLM_PROVIDER`, `LLM_API_KEY` | AI provider name and API key. The current AI client uses OpenAI. |
| `LLM_MODEL`, `LLM_MODEL_FAST` | Main and optional lower-cost model names. AI features need `LLM_API_KEY` and `LLM_MODEL`. |
| `AI_TIMEOUT_SECONDS`, `AI_MAX_OUTPUT_TOKENS` | AI request timeout and maximum output token budget. |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Optional Langfuse tracing credentials. |
| `LANGFUSE_BASE_URL` | Langfuse endpoint; default is the hosted Langfuse service. |
| `LANGFUSE_CAPTURE_CONTENT` | Whether traces include prompt and response content. Set false when only timings and token usage should be recorded. |
| `GEOCODER_BASE_URL` | Geocoding service endpoint. Defaults to OpenStreetMap Nominatim. |
| `GEOCODER_API_KEY` | API key if the selected geocoder requires one. |
| `GEOCODER_USER_AGENT` | Identifying User-Agent for geocoding requests; use a real contact address with public Nominatim. |
| `GEOCODER_MIN_INTERVAL_SECONDS` | Minimum gap between geocoding requests. Respect the selected provider's usage policy. |
| `EMAIL_PROVIDER` | `console` logs email content for development; `resend` sends email through Resend. |
| `RESEND_API_KEY`, `EMAIL_FROM` | Resend API key and verified sender address when `EMAIL_PROVIDER=resend`. |
| `ENABLE_DEV_ROUTES` | Enables development-only routes. Must be false in production or with live PayPal. |
| `SIMULATED_CLOCK` | Enables the development clock controls. Must be false in production or with live PayPal. |
| `ENABLE_JOBS` | Enables scheduled work such as unpaid-booking release and payment recovery. Requires a ready database. |
| `TEST_DATABASE_URL` | Optional, isolated database for integration tests. Tests may empty its tables; never point it at non-disposable data. |

`backend/.env.example` contains non-secret starting values and comments. Keep local secrets in `.env` or a deployment secret manager.

### Generate data-protection keys

Generate a Fernet-compatible encryption key and a separate hash key with the installed Python dependencies:

```powershell
.\.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
.\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the first value in `DATA_ENCRYPTION_KEY` and the second in `PHONE_HASH_KEY`. Keep durable, access-controlled backups of both keys. Losing the encryption key makes phone numbers encrypted by it unreadable. To rotate the encryption key, retain prior keys in the comma-separated value until existing data has been re-encrypted.

## Run the API

From the `backend` directory:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The health endpoint is `GET http://localhost:8000/health`. In development, FastAPI's Swagger UI is at `/docs`; API docs and the OpenAPI schema are disabled in production.

The app can start with optional services unconfigured, but dependent capabilities will be unavailable. Database-backed requests require `DATABASE_URL` and applied migrations. Inspect the startup logs and `/health` when diagnosing configuration.

## Database migrations

Alembic reads `DATABASE_URL` from `backend/.env`; credentials are not stored in `alembic.ini`. Run commands from `backend`:

```powershell
# Apply all checked-in migrations.
.\.venv\Scripts\python -m alembic upgrade head

# See the current database revision.
.\.venv\Scripts\python -m alembic current

# Create a migration after changing SQLAlchemy models.
.\.venv\Scripts\python -m alembic revision --autogenerate -m "describe the schema change"
```

Review autogenerated migrations before committing them. Test both upgrade and downgrade behavior against a disposable database before deploying schema changes.

## Tests

Run the backend tests from `backend`:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Pytest configuration is in `pytest.ini`. Most tests use isolated fixtures. Tests that require a live database can use `TEST_DATABASE_URL`; that database is cleared by the integration tests. Use only a newly provisioned, disposable test database and never use production, staging, or a developer's working database.

## Application structure

| Directory | Responsibility |
|---|---|
| `app/routers/public` | Public search, business details, documents, reviews, compliance, and location endpoints. |
| `app/routers/client` | Signed-in client bookings, account management, reviews, waitlists, and assistant endpoints. |
| `app/routers/owner` | Business setup and management, schedules, staff, services, bookings, decisions, photos, and daily workspace endpoints. |
| `app/routers/checkout.py`, `app/routers/webhooks.py` | Checkout links and PayPal event handling. |
| `app/models` and `app/schemas` | SQLAlchemy persistence models and validated API input/output types. |
| `app/rules` | Booking, scheduling, and policy logic kept separate from transport and persistence. |
| `app/auth` and `app/security` | Token verification and protection of sensitive data. |
| `app/payments`, `app/media`, `app/notifications`, `app/geo` | Integrations with payment, storage, email, and geocoding providers. |
| `app/ai` | AI requests, prompts, transcription, and optional tracing. |
| `app/jobs` | Scheduled background processing. |
| `app/templates` and `app/documents` | HTML templates and generated booking documents. |
| `alembic/versions` | Ordered PostgreSQL schema migrations. |
| `scripts` | Standalone setup or maintenance utilities. |

`app.main:create_app` assembles middleware, lifecycle setup, service clients, and routers. The lifespan initializes configured services and closes them during shutdown.

## PayPal Pro plan utility

After configuring sandbox PayPal credentials, the optional utility creates a PayPal product and monthly billing plan:

```powershell
.\.venv\Scripts\python -m scripts.create_pro_plan 499 INR
```

It prints a `PAYPAL_PRO_PLAN_ID` value. Add that value to the backend environment. Creating a plan changes the PayPal account; run it only against the intended sandbox or live account, and create the live plan separately when production is ready.

## Production checklist

- Set `APP_ENV=production`; keep `ENABLE_DEV_ROUTES=false` and `SIMULATED_CLOCK=false`.
- Set production `FRONTEND_URL` and `BACKEND_URL`, and allow only the production frontend origin.
- Set a production Supabase PostgreSQL connection, apply migrations, and configure database backups and access policies.
- Configure Firebase/Supabase authentication, PayPal and webhook verification, and other integrations that the deployed features require.
- Store credentials and data-protection keys in the host's secret manager, not in source control or frontend defines.
- Use `EMAIL_PROVIDER=resend` only after configuring a verified sender and valid API key.
- Decide whether Langfuse content capture is appropriate for the data handled by the application.
- Run backend tests and verify `/health` after deployment.
