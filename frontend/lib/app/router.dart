import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/auth_service.dart';
import '../features/account/booking_detail_screen.dart';
import '../features/account/move_booking_screen.dart';
import '../features/account/my_bookings_screen.dart';
import '../features/account/profile_screen.dart';
import '../features/account/waitlist_screen.dart';
import '../features/assistant/assistant_screen.dart';
import '../features/auth/client_sign_in_screen.dart';
import '../features/auth/owner_sign_in_screen.dart';
import '../features/booking/booking_flow_screen.dart';
import '../features/booking/checkout_screen.dart';
import '../features/business/business_screen.dart';
import '../features/home/for_business_screen.dart';
import '../features/home/for_clients_screen.dart';
import '../features/home/home_screen.dart';
import '../features/onboarding/onboarding_screen.dart';
import '../features/onboarding/setup_screen.dart';
import '../features/day/approvals_screen.dart';
import '../features/day/bookings_screen.dart';
import '../features/day/checkin_screen.dart';
import '../features/day/classes_screen.dart';
import '../features/day/reviews_screen.dart';
import '../features/owner/owner_today_screen.dart';
import '../features/settings/business_settings.dart';
import '../features/settings/location_settings.dart';
import '../features/settings/paypal_settings.dart';
import '../features/settings/photos_settings.dart';
import '../features/settings/plan_settings.dart';
import '../features/settings/policy_settings.dart';
import '../features/settings/services_settings.dart';
import '../features/settings/tax_settings.dart';
import '../features/settings/team_settings.dart';
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
      GoRoute(path: '/for-clients', builder: (context, state) => const ForClientsScreen()),
      GoRoute(path: '/for-business', builder: (context, state) => const ForBusinessScreen()),
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
            builder: (context, state) => BookingFlowScreen(
              slug: state.pathParameters['slug']!,
              query: state.uri.queryParameters,
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
        builder: (context, state) => const MyBookingsScreen(),
        routes: [
          GoRoute(
            path: 'bookings/:id',
            builder: (context, state) => BookingDetailScreen(bookingId: state.pathParameters['id']!),
            routes: [
              GoRoute(
                path: 'checkout',
                builder: (context, state) => CheckoutScreen(
                  bookingId: state.pathParameters['id']!,
                  checkoutUrl: state.uri.queryParameters['pay'],
                  until: DateTime.tryParse(state.uri.queryParameters['until'] ?? ''),
                  businessSlug: state.uri.queryParameters['from'],
                ),
              ),
              GoRoute(
                path: 'move',
                builder: (context, state) => MoveBookingScreen(bookingId: state.pathParameters['id']!),
              ),
            ],
          ),
          GoRoute(
            path: 'profile',
            builder: (context, state) => const ProfileScreen(),
          ),
          GoRoute(
            path: 'waitlist',
            builder: (context, state) => const WaitlistScreen(),
          ),
        ],
      ),
      GoRoute(
        path: '/assistant',
        builder: (context, state) => const AssistantScreen(),
      ),

      // ---------- owners ----------
      GoRoute(
        path: '/business',
        builder: (context, state) => const OwnerTodayScreen(),
        routes: [
          GoRoute(
            path: 'start',
            builder: (context, state) => const OnboardingScreen(),
          ),
          GoRoute(
            path: 'setup',
            builder: (context, state) => SetupScreen(
              businessId: state.uri.queryParameters['business'],
              policyVersion: int.tryParse(state.uri.queryParameters['policy'] ?? ''),
            ),
          ),
          GoRoute(
            path: 'bookings',
            builder: (context, state) => const OwnerBookingsScreen(),
          ),
          GoRoute(path: 'check-in', builder: (context, state) => const CheckInScreen()),
          GoRoute(
            path: 'approvals',
            builder: (context, state) => const ApprovalsScreen(),
          ),
          GoRoute(
            path: 'sessions',
            builder: (context, state) => const ClassesScreen(),
          ),
          GoRoute(
            path: 'reviews',
            builder: (context, state) => const OwnerReviewsScreen(),
          ),
          GoRoute(
            path: 'settings/:section',
            builder: (context, state) => switch (state.pathParameters['section']) {
              'profile' => const BusinessSettingsScreen(),
              'services' => const ServicesSettingsScreen(),
              'team' => const TeamSettingsScreen(),
              'policy' => const PolicySettingsScreen(),
              'photos' => const PhotosSettingsScreen(),
              'location' => const LocationSettingsScreen(),
              'tax' => const TaxSettingsScreen(),
              'paypal' => const PayPalSettingsScreen(),
              'plan' => PlanSettingsScreen(checkOnOpen: state.uri.queryParameters['check'] == '1'),
              _ => const NotFoundScreen(),
            },
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

  // Clients sign in with their phone (Firebase); owners with email (Supabase).
  if (clientArea && !auth.isClientSignedIn) {
    return Uri(path: '/signin', queryParameters: {'from': here}).toString();
  }
  if (ownerArea && !auth.isOwnerSignedIn) {
    return Uri(path: '/business/signin', queryParameters: {'from': here}).toString();
  }
  final signedInHere = (path == '/signin' && auth.isClientSignedIn) || (path == '/business/signin' && auth.isOwnerSignedIn);
  if (signedInHere) {
    final from = state.uri.queryParameters['from'];
    // Only go back to our own pages (never to another site).
    if (from != null && from.startsWith('/') && !from.startsWith('//')) return from;
    return path == '/signin' ? '/my' : '/business';
  }
  return null;
}
