import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';

Map<String, dynamic> _map(Object? json) => Map<String, dynamic>.from(json as Map);

class Country {
  const Country(this.code, this.name);
  final String code;
  final String name;
}

final countriesProvider = FutureProvider<List<Country>>((ref) async {
  final json = await ref.watch(apiClientProvider).get('/api/geo/countries');
  return [for (final item in json as List) Country((item as Map)['code'] as String, item['name'] as String)];
});

/// Sensible starting values for a country; the owner can change them.
const defaultCurrency = {
  'IN': 'INR', 'US': 'USD', 'GB': 'GBP', 'AU': 'AUD', 'CA': 'CAD', 'AE': 'AED', 'SG': 'SGD', 'NZ': 'NZD',
  'IE': 'EUR', 'DE': 'EUR', 'FR': 'EUR', 'ES': 'EUR', 'IT': 'EUR', 'NL': 'EUR', 'PT': 'EUR', 'BE': 'EUR', 'AT': 'EUR',
};
const defaultTimezone = {
  'IN': 'Asia/Kolkata', 'US': 'America/New_York', 'GB': 'Europe/London', 'AU': 'Australia/Sydney',
  'CA': 'America/Toronto', 'AE': 'Asia/Dubai', 'SG': 'Asia/Singapore', 'NZ': 'Pacific/Auckland', 'IE': 'Europe/Dublin',
  'DE': 'Europe/Berlin', 'FR': 'Europe/Paris', 'ES': 'Europe/Madrid', 'IT': 'Europe/Rome', 'NL': 'Europe/Amsterdam',
  'PT': 'Europe/Lisbon', 'BE': 'Europe/Brussels', 'AT': 'Europe/Vienna',
};

class InterviewQuestion {
  const InterviewQuestion({required this.id, required this.text, required this.kind, required this.options, required this.allowOther});

  final String id;
  final String text;
  final String kind;          // text, single_choice, multi_choice, yes_no, number
  final List<String> options;
  final bool allowOther;

  factory InterviewQuestion.fromJson(Map<String, dynamic> json) => InterviewQuestion(
        id: json['id'] as String,
        text: json['text'] as String,
        kind: json['kind'] as String? ?? 'text',
        options: [for (final o in (json['options'] as List? ?? const [])) o.toString()],
        allowOther: json['allow_other'] as bool? ?? false,
      );
}

class InterviewTurn {
  const InterviewTurn({required this.ready, required this.summary, required this.questions, required this.round, required this.maxRounds});

  final bool ready;
  final String summary;
  final List<InterviewQuestion> questions;
  final int round;
  final int maxRounds;

  factory InterviewTurn.fromJson(Map<String, dynamic> json) => InterviewTurn(
        ready: json['status'] == 'ready',
        summary: json['summary'] as String? ?? '',
        questions: [for (final q in (json['questions'] as List? ?? const [])) InterviewQuestion.fromJson(_map(q))],
        round: (json['round'] as num?)?.toInt() ?? 0,
        maxRounds: (json['max_rounds'] as num?)?.toInt() ?? 3,
      );
}

/// The AI's draft, kept as the backend's own JSON so it goes back exactly as the backend expects.
class DraftResult {
  const DraftResult({required this.draft, required this.warnings, required this.preview});

  final Map<String, dynamic> draft;
  final List<String> warnings;
  final Map<String, dynamic> preview;

  factory DraftResult.fromJson(Map<String, dynamic> json) => DraftResult(
        draft: _map(json['draft']),
        warnings: [for (final w in (json['warnings'] as List? ?? const [])) w.toString()],
        preview: _map(json['policy_preview'] ?? const {}),
      );
}

class Applied {
  const Applied({required this.businessId, required this.slug, required this.policyVersion});

  final String businessId;
  final String slug;
  final int policyVersion;
}

class OnboardingApi {
  const OnboardingApi(this._api);

  final ApiClient _api;

  Map<String, Object?> _base(String description, List<Map<String, String>> answers, String country, String currency, String timezone) => {
        'description': description,
        'answers': answers,
        'country_code': country,
        'currency': currency,
        'timezone': timezone,
      };

  Future<InterviewTurn> interview({
    required String description,
    required List<Map<String, String>> answers,
    required String country,
    required String currency,
    required String timezone,
    required int round,
  }) async =>
      InterviewTurn.fromJson(_map(await _api.post('/api/owner/onboarding/interview',
          body: {..._base(description, answers, country, currency, timezone), 'round': round})));

  Future<DraftResult> draft({
    required String description,
    required List<Map<String, String>> answers,
    required String country,
    required String currency,
    required String timezone,
  }) async =>
      DraftResult.fromJson(_map(await _api.post('/api/owner/onboarding/draft',
          body: _base(description, answers, country, currency, timezone))));

  Future<Applied> apply(Map<String, dynamic> draft) async {
    final json = _map(await _api.post('/api/owner/onboarding/apply', body: draft));
    return Applied(
      businessId: json['business_id'].toString(),
      slug: json['slug'] as String? ?? '',
      policyVersion: (json['policy_version'] as num).toInt(),
    );
  }
}

final onboardingApiProvider = Provider<OnboardingApi>((ref) => OnboardingApi(ref.watch(apiClientProvider)));
