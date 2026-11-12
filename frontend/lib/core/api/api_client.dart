import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_service.dart';
import '../config.dart';
import 'api_exception.dart';

/// The one way the app talks to the Rebookly backend.
///
/// * Adds the right sign-in token: the owner's (Supabase) for /api/owner/..., the client's (Firebase)
///   for everything else, falling back to whichever one exists.
/// * Turns every failure into an [ApiException] with a readable message.
/// * Returns the decoded JSON (a Map or a List); repositories turn it into typed models.
class ApiClient {
  ApiClient({Dio? dio, required Future<String?> Function(String path) readToken})
      : _dio = dio ?? Dio(),
        _readToken = readToken {
    _dio.options = BaseOptions(
      baseUrl: AppConfig.apiBaseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
      sendTimeout: const Duration(seconds: 30),
      headers: {'Accept': 'application/json'},
    );
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        try {
          final token = await _readToken(options.path);
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
        } catch (_) {
          // No token: the request goes without one, and the backend answers "sign in first" if it needs one.
        }
        handler.next(options);
      },
    ));
  }

  final Dio _dio;
  final Future<String?> Function(String path) _readToken;

  Future<dynamic> get(String path, {Map<String, Object?>? query}) =>
      _send(() => _dio.get<dynamic>(path, queryParameters: _clean(query)));

  Future<dynamic> post(String path, {Object? body, Map<String, Object?>? query}) =>
      _send(() => _dio.post<dynamic>(path, data: body, queryParameters: _clean(query)));

  Future<dynamic> put(String path, {Object? body}) => _send(() => _dio.put<dynamic>(path, data: body));

  /// Sends files (photos, voice recordings) as a form.
  Future<dynamic> postForm(String path, FormData form) => _send(() => _dio.post<dynamic>(path, data: form));

  Future<dynamic> patch(String path, {Object? body}) => _send(() => _dio.patch<dynamic>(path, data: body));

  Future<dynamic> delete(String path) => _send(() => _dio.delete<dynamic>(path));

  Future<dynamic> _send(Future<Response<dynamic>> Function() request) async {
    try {
      final response = await request();
      return response.data;
    } on DioException catch (error) {
      throw ApiException.from(error);
    }
  }

  static Map<String, Object?>? _clean(Map<String, Object?>? query) {
    if (query == null) return null;
    return {
      for (final entry in query.entries)
        if (entry.value != null && entry.value.toString().isNotEmpty) entry.key: entry.value,
    };
  }
}

final apiClientProvider = Provider<ApiClient>((ref) {
  final auth = ref.read(authServiceProvider);
  return ApiClient(readToken: (path) async {
    if (path.startsWith('/api/owner')) return auth.ownerToken();
    return await auth.clientToken() ?? auth.ownerToken();
  });
});
