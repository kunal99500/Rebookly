import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';

class Photo {
  const Photo({required this.url, required this.thumbUrl, this.width, this.height, this.altText});

  final String url;
  final String thumbUrl;
  final int? width;
  final int? height;
  final String? altText;

  static Photo? fromJson(Object? json) {
    if (json is! Map) return null;
    return Photo(
      url: json['url'] as String,
      thumbUrl: (json['thumb_url'] ?? json['url']) as String,
      width: (json['width'] as num?)?.toInt(),
      height: (json['height'] as num?)?.toInt(),
      altText: json['alt_text'] as String?,
    );
  }
}

class ServiceItem {
  const ServiceItem({
    required this.id,
    required this.name,
    required this.durationMinutes,
    required this.price,
    required this.deposit,
    required this.paymentOptions,
    required this.kind,
    required this.bookingMode,
    this.description,
    this.photo,
  });

  final String id;
  final String name;
  final String? description;
  final int durationMinutes;
  final String price;
  final String deposit;
  final List<String> paymentOptions;
  final String kind;          // "main" or "add_on"
  final String bookingMode;   // "appointment" or "class"
  final Photo? photo;

  bool get isAddOn => kind == 'add_on';
  bool get isClass => bookingMode == 'class';

  factory ServiceItem.fromJson(Map<String, dynamic> json) => ServiceItem(
        id: json['id'].toString(),
        name: json['name'] as String,
        description: json['description'] as String?,
        durationMinutes: (json['duration_minutes'] as num).toInt(),
        price: json['price'].toString(),
        deposit: (json['deposit'] ?? '0').toString(),
        paymentOptions: [for (final option in (json['payment_options'] as List? ?? const [])) option.toString()],
        kind: json['kind'] as String? ?? 'main',
        bookingMode: json['booking_mode'] as String? ?? 'appointment',
        photo: Photo.fromJson(json['photo']),
      );
}

class BusinessPage {
  const BusinessPage({
    required this.name,
    required this.slug,
    required this.category,
    required this.timezone,
    required this.currency,
    required this.services,
    required this.gallery,
    required this.ratingCount,
    required this.policyLines,
    required this.freeCancelHours,
    required this.graceMinutes,
    required this.depositTiming,
    this.description,
    this.address,
    this.cover,
    this.ratingAverage,
    this.depositBanner,
    this.ownerNote,
  });

  final String name;
  final String slug;
  final String? description;
  final String category;
  final String timezone;
  final String currency;
  final String? address;
  final Photo? cover;
  final List<Photo> gallery;
  final String? ratingAverage;
  final int ratingCount;
  final List<ServiceItem> services;
  final List<String> policyLines;
  final int freeCancelHours;
  final int graceMinutes;
  final String depositTiming;   // business_page, booking_start or checkout
  final String? depositBanner;  // shown on this page when the owner chose "business_page"
  final String? ownerNote;

  List<ServiceItem> get mainServices => services.where((s) => !s.isAddOn).toList();
  List<ServiceItem> get addOns => services.where((s) => s.isAddOn).toList();

  factory BusinessPage.fromJson(Map<String, dynamic> json) {
    final rating = json['rating'] as Map? ?? const {};
    final policy = json['policy'] as Map? ?? const {};
    final notice = json['deposit_notice'] as Map? ?? const {};
    final summary = policy['summary'];
    return BusinessPage(
      name: json['name'] as String,
      slug: json['slug'] as String,
      description: json['description'] as String?,
      category: json['category'] as String? ?? 'other',
      timezone: json['timezone'] as String? ?? 'UTC',
      currency: json['currency'] as String? ?? 'USD',
      address: json['address'] as String?,
      cover: Photo.fromJson(json['cover']),
      gallery: (json['gallery'] as List? ?? const []).map(Photo.fromJson).whereType<Photo>().toList(),
      ratingAverage: rating['average']?.toString(),
      ratingCount: (rating['count'] as num?)?.toInt() ?? 0,
      services: [
        for (final item in (json['services'] as List? ?? const []))
          ServiceItem.fromJson(Map<String, dynamic>.from(item as Map)),
      ],
      policyLines: summary is List
          ? [for (final line in summary) line.toString()]
          : (summary == null ? const [] : [summary.toString()]),
      freeCancelHours: (policy['free_cancel_hours'] as num?)?.toInt() ?? 0,
      graceMinutes: (policy['grace_minutes'] as num?)?.toInt() ?? 0,
      depositTiming: notice['timing'] as String? ?? 'booking_start',
      depositBanner: notice['banner'] as String?,
      ownerNote: notice['owner_note'] as String?,
    );
  }
}

final businessPageProvider = FutureProvider.autoDispose.family<BusinessPage, String>((ref, slug) async {
  final json = await ref.watch(apiClientProvider).get('/api/public/businesses/${Uri.encodeComponent(slug)}');
  return BusinessPage.fromJson(Map<String, dynamic>.from(json as Map));
});
