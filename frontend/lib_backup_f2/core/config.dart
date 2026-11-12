/// Settings for the app. Values passed at build time with --dart-define (or --dart-define-from-file)
/// win; otherwise these development defaults are used.
/// Nothing secret lives here: the Supabase anon/publishable key is designed to be public,
/// and the backend checks every request.
abstract final class AppConfig {
  static const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000');
  static const supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://okbnsvwbizmtpwjerxjx.supabase.co',
  );
  static const supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: 'sb_publishable_22EMwGJwOSxNzQ3P94v0uQ_Vnk6SvcH',
  );

  static bool get authConfigured => supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;
}