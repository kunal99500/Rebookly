/// Settings for the app. Values passed at build time with --dart-define (or --dart-define-from-file) win;
/// otherwise these development defaults are used.
///
/// Nothing secret lives here: the Supabase publishable key and the Firebase web config are designed to be
/// public (every browser receives them), and the backend checks every request.
abstract final class AppConfig {
    static const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'https://rebookly-vlee.onrender.com');

  // Supabase: business owners sign in with email and password.
  static const supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://okbnsvwbizmtpwjerxjx.supabase.co',
  );
  static const supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY', defaultValue: 'sb_publishable_22EMwGJwOSxNzQ3P94v0uQ_Vnk6SvcH');

  // Firebase: clients sign in with a code sent to their phone.
  // Firebase console -> Project settings -> Your apps -> Web app -> "SDK setup and configuration" (Config).
  static const firebaseApiKey = String.fromEnvironment('FIREBASE_API_KEY', defaultValue: '');
  static const firebaseAuthDomain = String.fromEnvironment('FIREBASE_AUTH_DOMAIN', defaultValue: '');
  static const firebaseProjectId = String.fromEnvironment('FIREBASE_PROJECT_ID', defaultValue: '');
  static const firebaseAppId = String.fromEnvironment('FIREBASE_APP_ID', defaultValue: '');
  static const firebaseMessagingSenderId = String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID', defaultValue: '');

  static bool get authConfigured =>
      supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty && !supabaseAnonKey.startsWith('PASTE_');
  static bool get firebaseConfigured =>
      firebaseApiKey.isNotEmpty && firebaseProjectId.isNotEmpty && firebaseAppId.isNotEmpty;
}

