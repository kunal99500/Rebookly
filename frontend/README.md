# Rebookly frontend

The frontend is a Flutter web application for both people booking appointments and businesses managing their day-to-day operations. It uses clean browser paths (for example, `/b/example/book`) so links can be shared and browser navigation works as expected.

## Requirements and setup

- Flutter 3.27 or newer and Dart 3.5 or newer (see `pubspec.yaml`)
- Chrome for local browser development
- A running Rebookly backend for API-backed functionality

From this directory:

```powershell
flutter pub get
```

The app's build-time settings are declared in `lib/core/config.dart`. Supply them with `--dart-define` or `--dart-define-from-file`; do not put server secrets in either. The `dart_defines.json` file used by `run.ps1` is local and Git-ignored. Do not commit it.

### Run locally

Start the backend on port `8000` and make sure its `FRONTEND_URL` is `http://localhost:5000`. Then run the web app with your local service configuration:

```powershell
flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_PUBLISHABLE_KEY --dart-define=FIREBASE_API_KEY=YOUR_FIREBASE_WEB_API_KEY --dart-define=FIREBASE_AUTH_DOMAIN=YOUR_PROJECT.firebaseapp.com --dart-define=FIREBASE_PROJECT_ID=YOUR_FIREBASE_PROJECT_ID --dart-define=FIREBASE_APP_ID=YOUR_FIREBASE_WEB_APP_ID --dart-define=FIREBASE_MESSAGING_SENDER_ID=YOUR_FIREBASE_SENDER_ID
```

To disable authentication integrations for a local UI run, explicitly pass empty Supabase defines and leave out the Firebase defines; the corresponding sign-in and API-backed functionality will not be available. The default development web origin (`localhost:5000`) must match the backend CORS setting.

| Define | Used for |
|---|---|
| `API_BASE_URL` | Rebookly backend base URL. Use `http://localhost:8000` locally and the deployed HTTPS API URL for a production build. |
| `SUPABASE_URL` | Supabase project URL for business-owner email sign-in. |
| `SUPABASE_ANON_KEY` | Supabase publishable/anon key for the client app. This is intentionally client-visible; never use the service-role key. |
| `FIREBASE_API_KEY` | Firebase web-app API key for client phone sign-in. |
| `FIREBASE_AUTH_DOMAIN` | Firebase web app auth domain. |
| `FIREBASE_PROJECT_ID` | Firebase project ID. |
| `FIREBASE_APP_ID` | Firebase web-app ID. |
| `FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID. |

Firebase web configuration and Supabase publishable keys are public client configuration, not backend credentials. The backend verifies identity tokens and enforces authorization. Configure the relevant localhost and production domains in Firebase and Supabase consoles.

## Features and routes

### Public and client experience

| Route | Purpose |
|---|---|
| `/` | Landing page and entry points for clients and businesses. |
| `/for-clients`, `/for-business` | Information pages for each audience. |
| `/search?q=...&category=...` | Search public businesses and services. |
| `/b/:slug` | Business profile, services, policies, and booking entry point. |
| `/b/:slug/book` | Service/class selection (including a class selected by the `class` query parameter), staff and time selection, deposit and policy details, booking review, and checkout. |
| `/signin` | Client phone sign-in. |
| `/my` | Upcoming and past client bookings. |
| `/my/bookings/:id` | Booking details, ticket/check-in code, cancellation, review, and available booking actions. |
| `/my/bookings/:id/checkout` | Continue payment through the checkout link. |
| `/my/bookings/:id/move` | Move a booking to an available time. |
| `/my/waitlist` | View or leave waitlists and respond to offers. |
| `/my/profile` | Client profile, reminders, sign-out, and account deletion. |
| `/assistant` | Client assistant. |

### Business-owner experience

| Route | Purpose |
|---|---|
| `/business/signin` | Owner email sign-in. |
| `/business` | Business workspace and daily overview. |
| `/business/start` | Guided business onboarding. |
| `/business/setup` | Setup checklist, policy review, and go-live actions. |
| `/business/bookings` | Manage bookings. |
| `/business/check-in` | Check in clients. |
| `/business/approvals` | Review requests that need owner approval. |
| `/business/sessions` | Manage class sessions. |
| `/business/reviews` | View business reviews. |
| `/business/settings/profile` | Business profile. |
| `/business/settings/services` | Services and extras. |
| `/business/settings/team` | Staff and team setup. |
| `/business/settings/policy` | Booking and cancellation policies. |
| `/business/settings/photos` | Business photos. |
| `/business/settings/location` | Business location. |
| `/business/settings/tax` | Tax details. |
| `/business/settings/paypal` | PayPal connection and payment settings. |
| `/business/settings/plan` | Subscription plan settings. |

Private client and owner routes redirect to the appropriate sign-in page and return the user to the requested internal route after sign-in. These frontend guards improve the flow but are not an authorization boundary; the backend checks permissions on every protected request.

## Authentication and API

- Clients sign in with Firebase phone authentication.
- Business owners sign in with Supabase email and password.
- `lib/core/auth/` contains the shared auth service.
- `lib/core/api/` contains the API client and API error handling. Authenticated requests include the signed-in user's token.
- The backend verifies Firebase and Supabase tokens and applies access controls.

Do not add service-role keys, database URLs, PayPal secrets, encryption keys, or other server credentials to this app. Anything supplied using `--dart-define` is bundled into the client and can be inspected by users.

## Code layout

```text
lib/
  main.dart                 Flutter setup, URL strategy, services, locale and app start
  app/
    app.dart                Top-level app widget
    router.dart             Route table and sign-in redirects
    theme.dart              Theme
    tokens.dart             Reusable colors, spacing, and typography tokens
  core/
    api/                    HTTP client and readable backend errors
    auth/                   Firebase and Supabase sign-in state
    config.dart             Compile-time, non-secret client configuration
    format/                 Money and business-time-zone formatting
    i18n/                   Locale loading and language selection
  features/
    account/                Client bookings, profile, booking details, waitlists
    assistant/              Client assistant
    auth/                   Client and owner sign-in pages
    booking/                Booking selection, checkout, and waitlist flow
    business/               Public business profile
    day/                    Owner bookings, check-in, approvals, classes, reviews
    home/                   Landing and audience information
    onboarding/             Business setup and launch checklist
    owner/                  Owner workspace
    planned/                Informational pages for planned features
    search/                 Business discovery
    settings/               Owner business and account settings
  shared/                   Reusable UI, shells, layout, and status widgets
assets/
  fonts/                    Bundled Figtree and Bricolage Grotesque fonts
  i18n/                     English source and translated JSON strings
test/                       Flutter unit and widget tests
web/                        Browser entry point, icons, and install manifest
```

## UI conventions

- Shared design tokens and theme live in `lib/app/tokens.dart` and `lib/app/theme.dart`.
- Figtree and Bricolage Grotesque are bundled under `assets/fonts`; the app does not fetch fonts from Google at runtime.
- Booking money and payment states are displayed as returned by the backend; the frontend must not recalculate business prices or booking rules.
- Appointment times should be displayed in the business's configured time zone.
- Respect reduced-motion preferences and provide useful loading, empty, and error states.

## Languages and translations

Interface strings are in `assets/i18n/{language}.json`. English (`en.json`) is the source and fallback. Current locale files are Arabic, Bengali, English, Spanish, French, Gujarati, Hindi, Indonesian, Kannada, Malayalam, Marathi, Punjabi, Portuguese, Tamil, Telugu, and Urdu.

Language selection follows the device locale where supported, can be changed in the app, and is remembered. Arabic and Urdu use right-to-left layout. Translation files marked `_review` are drafts and must be reviewed by a fluent speaker before release, particularly text about payments, deposits, cancellations, and refunds.

The optional `tool/translate_i18n.py` script drafts missing translations with the OpenAI API. It needs the Python `openai` package and `OPENAI_API_KEY`; do not commit the key. It only fills missing strings, validates placeholders, and marks generated files for human review.

## Test and analyze

Run from `frontend`:

```powershell
flutter analyze
flutter test
```

Tests cover account and booking data, API errors, booking URL state, money/time formatting, hold-ticket UI, and localization consistency. Add or update tests when changing route behavior, data formatting, API error handling, or localization.

## Build and deploy

Build the static web app with production configuration:

```powershell
flutter build web --release --dart-define=API_BASE_URL=https://YOUR_API_HOST --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_PUBLISHABLE_KEY --dart-define=FIREBASE_API_KEY=YOUR_FIREBASE_WEB_API_KEY --dart-define=FIREBASE_AUTH_DOMAIN=YOUR_PROJECT.firebaseapp.com --dart-define=FIREBASE_PROJECT_ID=YOUR_FIREBASE_PROJECT_ID --dart-define=FIREBASE_APP_ID=YOUR_FIREBASE_WEB_APP_ID --dart-define=FIREBASE_MESSAGING_SENDER_ID=YOUR_FIREBASE_SENDER_ID
```

This writes the site to `build/web`. The Firebase Hosting configuration in `firebase.json` publishes that directory, routes unknown paths to `index.html` for client-side navigation, caches static assets, and avoids caching the entry page.

After authenticating/configuring the Firebase CLI for the intended project, deploy from this directory:

```powershell
# If no Firebase project is selected, choose one first:
firebase use --add

firebase deploy --only hosting
```

Before release, verify the production API URL, backend CORS origin, Firebase authorized domains, Supabase redirect/site URLs, and that no server-only credentials were included in the build.
