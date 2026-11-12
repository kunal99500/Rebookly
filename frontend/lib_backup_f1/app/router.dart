import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/auth_service.dart';
import '../features/auth/client_sign_in_screen.dart';
import '../features/auth/owner_sign_in_screen.dart';
import '../features/business/business_screen.dart';
import '../features/home/home_screen.dart';
import '../features/owner/owner_today_screen.dart';
import '../features/planned/planned_screen.dart';
import '../features/search/search_screen.dart';

/// Every page has a real address, so links can be shared and the browser's back button works.
///
/// Who may see what:
///   * public: home, search, business pages (clients browse without signing in)
///   * clients: /my... and the assistant (phone sign-in)
///   * owners: /business... (email sign-in)
/// The backend checks permissions on every request anyway; these guards just send people to sign in first.
final routerProvider = Provider<GoRouter>((ref) {
  final auth = ref.read(authServiceProvider);
  return GoRouter(
    initialLocation: '/',
    refreshListenable: auth,
    redirect: (context, state) => _guard(auth, state),
    errorBuilder: (context, state) => const NotFoundScreen(),
    routes: [
      // ---------- public ----------
      GoRoute(path: '/', builder: (context, state) => const HomeScreen()),
      GoRoute(
        path: '/search',
        builder: (context, state) => SearchScreen(
          text: state.uri.queryParameters['q'] ?? '',
          category: state.uri.queryParameters['category'],
        ),
      ),
      GoRoute(
        path: '/b/:slug',
        builder: (context, state) => BusinessScreen(slug: state.pathParameters['slug']!),
        routes: [
          GoRoute(
            path: 'book',
            builder: (context, state) => const PlannedScreen(
              title: 'Book a time',
              purpose: 'Choose services and extras, see the exact deposit and cancellation rules, pick a time '
                  '(and a staff member if you like), then pay the hold with PayPal. Full classes and busy days '
                  'offer a waitlist.',
              milestone: 'F2: the booking flow',
            ),
          ),
        ],
      ),

      // ---------- sign-in ----------
      GoRoute(path: '/signin', builder: (context, state) => const ClientSignInScreen()),
      GoRoute(path: '/business/signin', builder: (context, state) => const OwnerSignInScreen()),

      // ---------- clients ----------
      GoRoute(
        path: '/my',
        builder: (context, state) => const PlannedScreen(
          title: 'My bookings',
          purpose: 'Upcoming and past visits with what is held for each, receipts, check-in codes, and '
              'one-tap reschedule or cancel with the exact cost shown first.',
          milestone: 'F3: your account',
        ),
        routes: [
          GoRoute(
            path: 'bookings/:id',
            builder: (context, state) => const PlannedScreen(
              title: 'Booking details',
              purpose: 'Services, time, staff, the hold ticket, receipts, and your check-in code.',
              milestone: 'F3: your account',
            ),
            routes: [
              GoRoute(
                path: 'move',
                builder: (context, state) => const PlannedScreen(
                  title: 'Move this booking',
                  purpose: 'Only times you can really move to are shown, with the same deposit and rules.',
                  milestone: 'F3: your account',
                ),
              ),
            ],
          ),
          GoRoute(
            path: 'profile',
            builder: (context, state) => const PlannedScreen(
              title: 'Your profile',
              purpose: 'Your name, your phone (shown masked), an optional email for reminders, and deleting your data.',
              milestone: 'F3: your account',
            ),
          ),
          GoRoute(
            path: 'waitlist',
            builder: (context, state) => const PlannedScreen(
              title: 'Waitlist',
              purpose: 'Times you are waiting for, and offers to book a freed time before they expire.',
              milestone: 'F3: your account',
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/assistant',
        builder: (context, state) => const PlannedScreen(
          title: 'Booking assistant',
          purpose: 'Ask about your bookings in your own words. Any change it suggests comes as a card you confirm.',
          milestone: 'F7: AI and polish',
        ),
      ),

      // ---------- owners ----------
      GoRoute(
        path: '/business',
        builder: (context, state) => const OwnerTodayScreen(),
        routes: [
          GoRoute(
            path: 'start',
            builder: (context, state) => const PlannedScreen(
              owner: true,
              title: 'Set up with AI',
              purpose: 'Describe your business, answer a few quick questions, then review the drafted services, '
                  'hours and cancellation policy before anything is saved.',
              milestone: 'F4: owner onboarding',
            ),
          ),
          GoRoute(
            path: 'setup',
            builder: (context, state) => const PlannedScreen(
              owner: true,
              title: 'Get ready to go live',
              purpose: 'Confirm your policy, add your location, tax details and photos, connect PayPal, then go live.',
              milestone: 'F4: owner onboarding',
            ),
          ),
          GoRoute(
            path: 'bookings',
            builder: (context, state) => const PlannedScreen(
              owner: true,
              title: 'Bookings',
              purpose: 'Your day by staff member, check-ins by QR code, no-shows, and moving or cancelling bookings.',
              milestone: 'F6: running the day',
            ),
          ),
          GoRoute(
            path: 'approvals',
            builder: (context, state) => const PlannedScreen(
              owner: true,
              title: 'Approvals',
              purpose: 'Fees waiting for your decision, with the reason: charge, lower or waive. Retry failed payments.',
              milestone: 'F6: running the day',
            ),
          ),
          GoRoute(
            path: 'sessions',
            builder: (context, state) => const PlannedScreen(
              owner: true,
              title: 'Classes',
              purpose: 'Upcoming class sessions, seats taken, and blocking a session.',
              milestone: 'F6: running the day',
            ),
          ),
          GoRoute(
            path: 'reviews',
            builder: (context, state) => const PlannedScreen(
              owner: true,
              title: 'Reviews',
              purpose: 'Verified reviews from attended visits. Reply publicly, or report a review to Rebookly.',
              milestone: 'F6: running the day',
            ),
          ),
          GoRoute(
            path: 'settings/:section',
            builder: (context, state) => PlannedScreen(
              owner: true,
              title: _settingsTitle(state.pathParameters['section']!),
              purpose: 'Change this part of your business. Every change is checked by the same rules as during setup.',
              milestone: 'F5: owner setup',
            ),
          ),
        ],
      ),
    ],
  );
});

String? _guard(AuthService auth, GoRouterState state) {
  final path = state.uri.path;
  final clientArea = path == '/my' || path.startsWith('/my/') || path == '/assistant';
  final ownerArea = (path == '/business' || path.startsWith('/business/')) && path != '/business/signin';
  final here = state.uri.toString();

  if (!auth.isSignedIn) {
    if (clientArea) return Uri(path: '/signin', queryParameters: {'from': here}).toString();
    if (ownerArea) return Uri(path: '/business/signin', queryParameters: {'from': here}).toString();
    return null;
  }
  if (path == '/signin' || path == '/business/signin') {
    final from = state.uri.queryParameters['from'];
    // Only go back to our own pages (never to another site).
    if (from != null && from.startsWith('/') && !from.startsWith('//')) return from;
    return path == '/signin' ? '/my' : '/business';
  }
  return null;
}

String _settingsTitle(String section) => switch (section) {
      'profile' => 'Business details',
      'services' => 'Services',
      'team' => 'Team and hours',
      'policy' => 'Cancellation policy',
      'photos' => 'Photos',
      'location' => 'Location',
      'tax' => 'Tax',
      'paypal' => 'PayPal',
      _ => 'Settings',
    };
