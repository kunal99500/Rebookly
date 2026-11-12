/// Settings passed at build time with --dart-define. Nothing secret lives in the app:
/// the Supabase anon key is designed to be public, and the backend checks every request.
abstract final class AppConfig {
  static const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000');
  static const supabaseUrl = String.fromEnvironment('SUPABASE_URL');
  static const supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');

  static bool get authConfigured => supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;
}
