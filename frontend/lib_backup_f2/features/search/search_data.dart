import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';

class SearchResult {
  const SearchResult({
    required this.slug,
    required this.name,
    required this.category,
    required this.currency,
    required this.ratingCount,
    this.city,
    this.distanceKm,
    this.ratingAverage,
    this.priceFrom,
    this.coverThumbUrl,
  });

  final String slug;
  final String name;
  final String category;
  final String? city;
  final double? distanceKm;
  final String? ratingAverage;  // decimal string from the backend, e.g. "4.60"
  final int ratingCount;
  final String? priceFrom;      // decimal string, shown with formatMoney
  final String currency;
  final String? coverThumbUrl;

  factory SearchResult.fromJson(Map<String, dynamic> json) => SearchResult(
        slug: json['slug'] as String,
        name: json['name'] as String,
        category: json['category'] as String? ?? 'other',
        city: json['city'] as String?,
        distanceKm: (json['distance_km'] as num?)?.toDouble(),
        ratingAverage: json['rating_average']?.toString(),
        ratingCount: (json['rating_count'] as num?)?.toInt() ?? 0,
        priceFrom: json['price_from']?.toString(),
        currency: json['currency'] as String? ?? 'USD',
        coverThumbUrl: json['cover_thumb_url'] as String?,
      );
}

class SearchResults {
  const SearchResults({required this.results, this.category, this.nearMe = false});

  final List<SearchResult> results;
  final String? category;   // what the backend understood, e.g. "barber"
  final bool nearMe;

  factory SearchResults.fromJson(Map<String, dynamic> json) => SearchResults(
        category: json['category'] as String?,
        nearMe: json['near_me'] as bool? ?? false,
        results: [
          for (final item in (json['results'] as List? ?? const []))
            SearchResult.fromJson(Map<String, dynamic>.from(item as Map)),
        ],
      );
}

/// What to search for. A record, so two identical searches share one request.
typedef SearchQuery = ({String text, String? category});

final searchProvider = FutureProvider.autoDispose.family<SearchResults, SearchQuery>((ref, query) async {
  final json = await ref.watch(apiClientProvider).get('/api/public/search', query: {
    'q': query.text,
    'category': query.category,
  });
  return SearchResults.fromJson(Map<String, dynamic>.from(json as Map));
});
