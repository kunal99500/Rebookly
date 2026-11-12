# Rebookly

Rebookly is an appointment-booking platform for local service businesses. It combines a Flutter web app for clients and business owners with a FastAPI backend. Businesses publish services, schedules, policies, and payment details; clients find a business, choose a service and time, and manage their bookings.

## Project documentation

- [Backend setup and operations](./backend/README.md)
- [Frontend setup, features, and deployment](./frontend/README.md)

## Repository layout

```text
backend/
  app/
    ai/             AI clients, prompts, and observability
    auth/           Supabase and Firebase token verification
    compliance/     Business compliance and policy helpers
    documents/      Booking documents and snapshots
    geo/            Address and geocoding support
    jobs/           Scheduled background work
    media/          Photo validation, processing, and storage
    models/         SQLAlchemy database models
    notifications/  Email senders and notification rules
    payments/       PayPal checkout, webhooks, and subscriptions
    routers/        Public, client, owner, checkout, and webhook APIs
    rules/          Booking, scheduling, and policy rules
    schemas/        API request and response schemas
    security/       Protection of sensitive client data
    services/       Shared application services
    templates/      HTML email and document templates
  alembic/          PostgreSQL schema migrations
  scripts/          Backend maintenance and setup scripts
  tests/            Backend test suite
frontend/
  lib/
    app/            App shell, routing, and visual design tokens
    core/           API, auth, config, formatting, and localization
    features/       Client and business-owner screens and workflows
    shared/         Reusable widgets and layouts
  assets/           Fonts and translated interface strings
  test/             Flutter widget and unit tests
  web/              Flutter web entry point and icons
```

## Prerequisites

- Python with `venv` support and pip
- Flutter 3.27 or newer (Dart 3.5 or newer)
- A PostgreSQL database for persistent backend features; Supabase Postgres is the configured provider
- Optional service accounts for Supabase Auth/Storage, Firebase phone and anonymous auth, PayPal, OpenAI, Langfuse, a geocoding provider, and Resend email

Most third-party integrations are optional in development. Features that require an unconfigured integration remain unavailable and the backend logs a warning.

## Local development

Set up the backend and frontend in separate terminals. Detailed environment setup and feature-specific options are in each component README.

1. Prepare backend dependencies and `backend/.env` using [backend/README.md](./backend/README.md).
2. Start the API from the `backend` directory:

   ```powershell
   .\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. Configure and start the Flutter app using [frontend/README.md](./frontend/README.md). Use port `5000` in development so the browser origin matches the backend's default `FRONTEND_URL`.
4. Check the API at `http://localhost:8000/health`. Interactive API documentation is available at `http://localhost:8000/docs` in development only.

The backend can start without a database or third-party credentials, but database-backed routes, sign-in, payments, email delivery, media uploads, and AI features require their respective configuration. Review the health response and backend logs when enabling these features.

## Quality checks

Run commands from the relevant component directory:

```powershell
# Backend
cd backend
.\.venv\Scripts\python -m pytest -q

# Frontend
cd ..\frontend
flutter analyze
flutter test
```

Backend integration tests use `TEST_DATABASE_URL` if configured. That database is emptied by the integration tests; use only a dedicated disposable test database, never a development, staging, or production database.

## Deployment overview

- The frontend is a Flutter web app. Build it with production `--dart-define` values and deploy the generated `frontend/build/web` directory to a static web host. Firebase Hosting configuration is in `frontend/firebase.json`.
- Deploy the backend as an ASGI application using `app.main:app`. Set its production environment variables in the hosting provider's secret manager, apply Alembic migrations, and configure the public frontend origin, database, authentication, and required integrations.
- Configure production Firebase, Supabase, and PayPal settings in their respective consoles. The frontend's Firebase web configuration and Supabase publishable key are client-visible; never put Supabase service-role credentials, database passwords, API secrets, encryption keys, or webhook secrets in frontend build defines.
- Keep `ENABLE_DEV_ROUTES` and `SIMULATED_CLOCK` disabled in production. The backend validates these safety settings.

Deployment is not a substitute for provider-side setup: configure allowed origins, redirect URLs, webhook endpoints, database access, storage policies, and secret rotation in the corresponding service consoles.

## Data and security notes

- The backend is the source of truth for booking rules, prices, availability, cancellation costs, and payment state.
- Client phone numbers are stored encrypted and indexed using a keyed hash. Back up `DATA_ENCRYPTION_KEY` securely; losing it prevents decrypting phone numbers already stored with that key.
- Use separate keys and credentials for local, test, staging, and production environments.
- Never commit `.env` files or local `dart_defines.json` files. The repository ignores these local configuration files; commit only non-secret examples.
- Treat user-generated content and AI output as untrusted input. Keep authorization and business rules enforced by the backend.
