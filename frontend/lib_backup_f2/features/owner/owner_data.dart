import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';

class OwnedBusiness {
  const OwnedBusiness({required this.id, required this.name, required this.slug, required this.status});

  final String id;
  final String name;
  final String slug;
  final String status;   // draft, live or paused

  bool get isLive => status == 'live';

  factory OwnedBusiness.fromJson(Map<String, dynamic> json) => OwnedBusiness(
        id: json['id'].toString(),
        name: json['name'] as String? ?? 'Your business',
        slug: json['slug'] as String? ?? '',
        status: json['status'] as String? ?? 'draft',
      );
}

class Briefing {
  const Briefing({
    required this.day,
    required this.summary,
    required this.aiWritten,
    required this.highlights,
    required this.suggestions,
    required this.refreshesLeft,
  });

  final String day;
  final String summary;
  final bool aiWritten;
  final List<String> highlights;
  final List<String> suggestions;
  final int refreshesLeft;

  factory Briefing.fromJson(Map<String, dynamic> json) => Briefing(
        day: json['day'] as String? ?? '',
        summary: json['summary'] as String? ?? '',
        aiWritten: json['ai_written'] as bool? ?? false,
        highlights: [for (final line in (json['highlights'] as List? ?? const [])) line.toString()],
        suggestions: [for (final line in (json['suggestions'] as List? ?? const [])) line.toString()],
        refreshesLeft: (json['refreshes_left'] as num?)?.toInt() ?? 0,
      );
}

/// The signed-in owner's businesses (most owners have one).
final ownedBusinessesProvider = FutureProvider.autoDispose<List<OwnedBusiness>>((ref) async {
  final json = await ref.watch(apiClientProvider).get('/api/owner/businesses');
  return [for (final item in json as List) OwnedBusiness.fromJson(Map<String, dynamic>.from(item as Map))];
});

/// Today's briefing for one business: saved once a day by the backend, so opening it again is instant.
final briefingProvider = FutureProvider.autoDispose.family<Briefing, String>((ref, businessId) async {
  final json = await ref.watch(apiClientProvider).get('/api/owner/businesses/$businessId/briefing');
  return Briefing.fromJson(Map<String, dynamic>.from(json as Map));
});

Future<Briefing> refreshBriefing(ApiClient api, String businessId) async {
  final json = await api.get('/api/owner/businesses/$businessId/briefing', query: {'refresh': 'true'});
  return Briefing.fromJson(Map<String, dynamic>.from(json as Map));
}
