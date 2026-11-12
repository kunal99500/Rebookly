# Rebookly web app (Flutter)

The client booking site and the business owner workspace, in one Flutter web app.

## Run it

**One-time setup** (needs Flutter 3.27 or newer):

```bash
flutter create --platforms web .   # adds any missing web files; our web/index.html, icons and manifest are kept
flutter pub get
```

**Start it in Chrome on port 5000** (the backend's `FRONTEND_URL` must be `http://localhost:5000` so the browser is allowed to call the API):

```bash
flutter run -d chrome --web-port 5000 \
  --dart-define=API_BASE_URL=http://localhost:8000 \
  --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=YOUR_ANON_KEY
```

On Windows PowerShell, put it on one line (or use a backtick ` at the end of each line instead of `\`).

**Checks:**

```bash
flutter analyze
flutter test
```

**Production build:** the same `--dart-define` values with `flutter build web --release`.

## What works now (F1 to F4)

| Page | Address | Live data |
|---|---|---|
| Home | `/` | Search box and category picks; an example hold ticket |
| Search | `/search?q=barber&category=barber` | `GET /api/public/search` |
| Business page | `/b/{slug}` | `GET /api/public/businesses/{slug}`: photos, services, extras, deposits, cancellation rules |
| Client sign-in | `/signin` | Supabase phone code |
| Owner sign-in / create account | `/business/signin` | Supabase email and password |
| Owner "Today" | `/business` | `GET /api/owner/businesses` and the daily briefing |
| **Booking flow** | `/b/{slug}/book` | Services and extras, deposit notice, times (by day, part of day and staff), review, PayPal |
| Class booking | `/b/{slug}/book?class={id}` | Sessions with seats left, review, PayPal |
| Checkout and confirmation | `/my/bookings/{id}/checkout` | Opens PayPal in a new tab and waits for the hold |
| Waitlist | from the time step | "Tell me if a time opens" |
| **My bookings** | `/my` | Coming up and past, waitlist offers banner |
| Booking details | `/my/bookings/{id}` | Ticket, QR check-in code, move, cancel (cost first), review, receipts |
| Move a booking | `/my/bookings/{id}/move` | Only times it can really move to |
| Waitlist | `/my/waitlist` | Offers to book a freed time, leave the list |
| Profile | `/my/profile` | Name, email for reminders (with code), sign out, delete my data |
| **Set up with AI** | `/business/start` | Describe, quick questions, editable draft, save |
| Setup checklist | `/business/setup` | Confirm the policy (rules-engine preview), what's left, go live, booking link |

## Sign-in

* **Clients:** Firebase phone codes. Set the five `FIREBASE_*` values (see `lib/core/config.dart`).
* **Business owners:** Supabase email and password (`SUPABASE_URL`, `SUPABASE_ANON_KEY`).
* The backend accepts both (see `backend_changes/`).

Every other address from the plan already exists and explains what it will do and in which step it arrives,
so the app can be clicked through end to end.

**Sign-in guards:** `/my...` and `/assistant` send people to phone sign-in; `/business...` sends them to
owner sign-in. After signing in they return to the page they wanted.

## How the code is organised

```
lib/
├── main.dart                 start-up: clean URLs, time zones, Supabase
├── app/                      tokens.dart (colours, spacing, type), theme.dart, router.dart, app.dart
├── core/
│   ├── config.dart           --dart-define settings
│   ├── api/                  ApiClient (adds the sign-in token) and ApiException (readable errors)
│   ├── auth/                 AuthService: phone codes, email sign-in, sign-out
│   └── format/               money (never recalculated) and times (always in the business's time zone)
├── shared/                   shells, hold ticket, money states, layout, loading/error/empty states, brand
└── features/                 home, auth, search, business, owner, planned
```

## Design system

* **Colours** (`app/tokens.dart`): ink, forest, paper, sage, line, plus one fixed colour per money state:
  held (blue), waiting for approval (amber), charged (ink), released (green), problem (red).
* **Type:** Bricolage Grotesque for headlines and amounts, Figtree for reading. Both are bundled in
  `assets/fonts` under the SIL Open Font License, so the app makes no requests to Google and text never jumps.
* **The hold ticket** (`shared/hold_ticket.dart`) is the signature element: what's booked above the tear line,
  the money and the cancellation timeline below it.
* **Rules the code follows:** money is shown exactly as the backend sends it; times are shown in the
  business's time zone; backend error messages are shown as written (they're written for people);
  motion respects "reduce motion".

## Languages

* Every sentence on screen comes from `assets/i18n/{language}.json`; English (`en.json`) is the source and the fallback.
* The language is taken from the device, can be changed with the globe button, and is remembered.
* Arabic and Urdu are shown right to left automatically.
* `hi.json` (Hindi) is a draft. Draft the other languages with `python tool/translate_i18n.py` (needs `OPENAI_API_KEY`).
  Every file says `_review`: **a fluent speaker must check each language before release**, especially lines about money.
* Screens converted so far: header and menus, home, "I want to book", "I own a business", both sign-in pages.
