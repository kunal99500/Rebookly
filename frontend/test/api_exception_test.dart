import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rebookly_frontend/core/api/api_exception.dart';

DioException _failure(int status, Object? data) {
  final request = RequestOptions(path: '/api/test');
  return DioException(
    requestOptions: request,
    response: Response(requestOptions: request, statusCode: status, data: data),
  );
}

void main() {
  test('a sentence from the backend is shown as it is', () {
    final problem = ApiException.from(_failure(409, {'detail': 'Sorry, that time was just taken. Please pick another.'}));
    expect(problem.message, 'Sorry, that time was just taken. Please pick another.');
    expect(problem.isConflict, isTrue);
  });

  test('form problems become readable lines', () {
    final problem = ApiException.from(_failure(422, {
      'detail': [
        {'loc': ['body', 'payment_option'], 'msg': 'Input should be deposit_held or full_held'},
        {'loc': ['body'], 'msg': 'Value error, Choose a state/region'},
      ],
    }));
    expect(problem.message, 'Payment option: Input should be deposit_held or full_held');
    expect(problem.details, contains('Choose a state/region'));
  });

  test('going-live problems keep their checklist', () {
    final problem = ApiException.from(_failure(409, {
      'detail': {'message': 'Not ready to go live yet', 'missing': ['Confirm a cancellation policy', 'Add a service']},
    }));
    expect(problem.message, 'Not ready to go live yet');
    expect(problem.details, ['Confirm a cancellation policy', 'Add a service']);
  });

  test('no response means a connection problem', () {
    final problem = ApiException.from(DioException(requestOptions: RequestOptions(path: '/x')));
    expect(problem.message, contains("Can't reach Rebookly"));
  });

  test('server errors never show technical details', () {
    final problem = ApiException.from(_failure(500, '<html>Internal Server Error</html>'));
    expect(problem.message, 'Rebookly had a problem with that. Try again in a moment.');
  });
}
