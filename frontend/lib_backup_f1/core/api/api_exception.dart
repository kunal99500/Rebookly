import 'package:dio/dio.dart';

/// A problem from the backend, turned into words a person can act on.
///
/// The backend sends `detail` in three shapes:
///   * a sentence ("Sorry, that time was just taken. Please pick another."),
///   * a list of form problems (FastAPI validation),
///   * an object with `message` and `missing` (for example when going live).
class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode, this.details = const []});

  final String message;
  final int? statusCode;
  final List<String> details;

  bool get isNotFound => statusCode == 404;
  bool get isConflict => statusCode == 409;
  bool get needsSignIn => statusCode == 401;

  factory ApiException.from(Object error) {
    if (error is ApiException) return error;
    if (error is! DioException) {
      return const ApiException("Something unexpected happened. Try again.");
    }
    final response = error.response;
    if (response == null) {
      return const ApiException("Can't reach Rebookly. Check your connection and try again.");
    }
    final status = response.statusCode;
    final data = response.data;
    final detail = data is Map ? data['detail'] : null;

    if (detail is String && detail.isNotEmpty) {
      return ApiException(detail, statusCode: status);
    }
    if (detail is List) {
      final problems = detail.whereType<Map>().map(_formProblem).where((m) => m.isNotEmpty).toList();
      return ApiException(
        problems.isEmpty ? 'Some details need another look.' : problems.first,
        statusCode: status,
        details: problems,
      );
    }
    if (detail is Map) {
      final missing = (detail['missing'] as List?)?.map((item) => item.toString()).toList() ?? const <String>[];
      return ApiException(
        detail['message']?.toString() ?? 'A few things need your attention.',
        statusCode: status,
        details: missing,
      );
    }
    if (status == 401) return ApiException('Your session ended. Sign in again.', statusCode: status);
    if (status == 403) return ApiException("You don't have access to that.", statusCode: status);
    if (status == 404) return ApiException("We couldn't find that.", statusCode: status);
    if (status == 429) return ApiException('Too many requests. Wait a moment and try again.', statusCode: status);
    if (status != null && status >= 500) {
      return ApiException('Rebookly had a problem with that. Try again in a moment.', statusCode: status);
    }
    return ApiException("That didn't work. Try again.", statusCode: status);
  }

  static String _formProblem(Map item) {
    final message = (item['msg'] ?? '').toString().replaceFirst('Value error, ', '');
    final location = item['loc'];
    if (location is List && location.length > 1) {
      final field = location.last.toString().replaceAll('_', ' ');
      if (int.tryParse(field) == null) return '${field[0].toUpperCase()}${field.substring(1)}: $message';
    }
    return message;
  }

  @override
  String toString() => message;
}
