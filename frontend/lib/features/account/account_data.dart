import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/config.dart';
import '../booking/booking_data.dart';

// ---------- what the backend sends ----------

class CancelPreview {
  const CancelPreview({required this.fee, required this.released, required this.currency, required this.reason, required this.needsOwnerApproval});

  final String fee;
  final String released;
  final String currency;
  final String reason;
  final bool needsOwnerApproval;

  bool get isFree => (num.tryParse(fee) ?? 0) == 0;

  factory CancelPreview.fromJson(Map<String, dynamic> json) => CancelPreview(
        fee: (json['fee'] ?? '0').toString(),
        released: (json['released'] ?? '0').toString(),
        currency: json['currency'] as String? ?? 'USD',
        reason: json['reason'] as String? ?? '',
        needsOwnerApproval: json['needs_owner_approval'] as bool? ?? false,
      );
}

/// A receipt, confirmation or release notice. Each opens as a page on the backend.
class DocumentLink {
  const DocumentLink({required this.title, required this.url, this.number, this.issuedAt});

  final String title;
  final String url;
  final String? number;
  final DateTime? issuedAt;

  static const _titles = {
    'booking_confirmation': 'Booking confirmation',
    'payment_receipt': 'Receipt',
    'fee_receipt': 'Fee receipt',
    'release_notice': 'Hold released',
  };

  static DocumentLink? fromJson(Map<String, dynamic> json) {
    final type = (json['type'] ?? json['document_type'] ?? '').toString();
    var url = (json['url'] ?? json['link'] ?? '').toString();
    final token = json['token']?.toString();
    if (url.isEmpty && token != null) url = '${AppConfig.apiBaseUrl}/api/public/documents/$token';
    if (url.startsWith('/')) url = '${AppConfig.apiBaseUrl}$url';
    if (url.isEmpty) return null;
    return DocumentLink(
      title: _titles[type] ?? (json['title']?.toString() ?? 'Document'),
      url: url,
      number: json['number']?.toString(),
      issuedAt: DateTime.tryParse((json['issued_at'] ?? '').toString()),
    );
  }
}

class ClientProfile {
  const ClientProfile({required this.name, this.phoneMasked, this.email, this.emailPending});

  final String name;
  final String? phoneMasked;
  final String? email;          // verified
  final String? emailPending;   // waiting for its code

  factory ClientProfile.fromJson(Map<String, dynamic> json) => ClientProfile(
        name: json['name'] as String? ?? '',
        phoneMasked: json['phone_masked'] as String?,
        email: json['email'] as String?,
        emailPending: json['email_pending'] as String?,
      );
}

class WaitlistItem {
  const WaitlistItem({
    required this.id,
    required this.businessName,
    required this.businessSlug,
    required this.visit,
    required this.wantedDate,
    required this.earliest,
    required this.latest,
    required this.status,
    this.offeredStartsAt,
    this.offerExpiresAt,
  });

  final String id;
  final String businessName;
  final String businessSlug;
  final String visit;
  final DateTime wantedDate;
  final String earliest;   // "16:00:00"
  final String latest;
  final String status;     // waiting, offered, booked, expired, removed
  final DateTime? offeredStartsAt;
  final DateTime? offerExpiresAt;

  bool get isOffer => status == 'offered';
  bool get isActive => status == 'waiting' || status == 'offered';

  factory WaitlistItem.fromJson(Map<String, dynamic> json) => WaitlistItem(
        id: json['id'].toString(),
        businessName: json['business_name'] as String? ?? '',
        businessSlug: json['business_slug'] as String? ?? '',
        visit: json['visit'] as String? ?? '',
        wantedDate: DateTime.parse(json['wanted_date'] as String),
        earliest: (json['earliest_time'] ?? '').toString(),
        latest: (json['latest_time'] ?? '').toString(),
        status: json['status'] as String? ?? 'waiting',
        offeredStartsAt: DateTime.tryParse((json['offered_starts_at'] ?? '').toString()),
        offerExpiresAt: DateTime.tryParse((json['offer_expires_at'] ?? '').toString()),
      );
}

class Review {
  const Review({required this.rating, this.comment, this.ownerReply, required this.visitedMonth});

  final int rating;
  final String? comment;
  final String? ownerReply;
  final String visitedMonth;

  factory Review.fromJson(Map<String, dynamic> json) => Review(
        rating: (json['rating'] as num).toInt(),
        comment: json['comment'] as String?,
        ownerReply: json['owner_reply'] as String?,
        visitedMonth: json['visited_month'] as String? ?? '',
      );
}

class ReviewStatus {
  const ReviewStatus({required this.canReview, required this.canEdit, this.review, this.reason});

  final Review? review;
  final bool canReview;
  final bool canEdit;
  final String? reason;

  factory ReviewStatus.fromJson(Map<String, dynamic> json) => ReviewStatus(
        review: json['review'] is Map ? Review.fromJson(Map<String, dynamic>.from(json['review'] as Map)) : null,
        canReview: json['can_review'] as bool? ?? false,
        canEdit: json['can_edit'] as bool? ?? false,
        reason: json['reason'] as String?,
      );
}

class DeletionCheck {
  const DeletionCheck({required this.canDelete, required this.reasons, required this.whatHappens});

  final bool canDelete;
  final List<String> reasons;
  final String whatHappens;

  factory DeletionCheck.fromJson(Map<String, dynamic> json) => DeletionCheck(
        canDelete: json['can_delete'] as bool? ?? false,
        reasons: [for (final r in (json['reasons'] as List? ?? const [])) r.toString()],
        whatHappens: json['what_happens'] as String? ?? '',
      );
}

typedef MoveOption = ({String raw, DateTime startsAt});

// ---------- reading ----------

Map<String, dynamic> _map(Object? json) => Map<String, dynamic>.from(json as Map);

/// A client with no profile yet simply has no bookings: the backend says "add your name first" (409).
final myBookingsProvider = FutureProvider.autoDispose<List<ClientBooking>>((ref) async {
  try {
    final json = await ref.watch(apiClientProvider).get('/api/client/bookings');
    return [for (final item in json as List) ClientBooking.fromJson(_map(item))];
  } on ApiException catch (problem) {
    if (problem.isConflict) return const [];
    rethrow;
  }
});

final bookingDetailProvider = FutureProvider.autoDispose.family<ClientBooking, String>((ref, id) async {
  return ClientBooking.fromJson(_map(await ref.watch(apiClientProvider).get('/api/client/bookings/$id')));
});

final bookingDocumentsProvider = FutureProvider.autoDispose.family<List<DocumentLink>, String>((ref, id) async {
  final json = await ref.watch(apiClientProvider).get('/api/client/bookings/$id/documents');
  final items = json is Map ? (json['documents'] as List? ?? const []) : json as List;
  return items.map((item) => DocumentLink.fromJson(_map(item))).whereType<DocumentLink>().toList();
});

final reviewStatusProvider = FutureProvider.autoDispose.family<ReviewStatus, String>((ref, id) async {
  return ReviewStatus.fromJson(_map(await ref.watch(apiClientProvider).get('/api/client/bookings/$id/review')));
});

/// Null when the client hasn't added their name yet.
final profileProvider = FutureProvider.autoDispose<ClientProfile?>((ref) async {
  try {
    return ClientProfile.fromJson(_map(await ref.watch(apiClientProvider).get('/api/client/profile')));
  } on ApiException catch (problem) {
    if (problem.isConflict || problem.isNotFound) return null;
    rethrow;
  }
});

final waitlistProvider = FutureProvider.autoDispose<List<WaitlistItem>>((ref) async {
  try {
    final json = await ref.watch(apiClientProvider).get('/api/client/waitlist');
    return [for (final item in json as List) WaitlistItem.fromJson(_map(item))];
  } on ApiException catch (problem) {
    if (problem.isConflict) return const [];
    rethrow;
  }
});

final deletionCheckProvider = FutureProvider.autoDispose<DeletionCheck>((ref) async {
  return DeletionCheck.fromJson(_map(await ref.watch(apiClientProvider).get('/api/client/account/deletion-check')));
});

// ---------- doing ----------

class AccountApi {
  const AccountApi(this._api);

  final ApiClient _api;

  Future<CancelPreview> cancelPreview(String id) async =>
      CancelPreview.fromJson(_map(await _api.get('/api/client/bookings/$id/cancel-preview')));

  Future<void> cancel(String id) => _api.post('/api/client/bookings/$id/cancel');

  Future<List<MoveOption>> moveOptions(String id, String day) async {
    final json = await _api.get('/api/client/bookings/$id/reschedule-options', query: {'day': day});
    return [
      for (final item in json as List)
        (raw: (item as Map)['starts_at'] as String, startsAt: DateTime.parse(item['starts_at'] as String)),
    ];
  }

  Future<void> move(String id, String startsAt) =>
      _api.post('/api/client/bookings/$id/reschedule', body: {'starts_at': startsAt});

  Future<void> saveName(String name) => _api.put('/api/client/profile', body: {'name': name});
  Future<void> addEmail(String email) => _api.post('/api/client/profile/email', body: {'email': email});
  Future<void> verifyEmail(String code) => _api.post('/api/client/profile/email/verify', body: {'code': code});
  Future<void> removeEmail() => _api.delete('/api/client/profile/email');

  Future<BookingStarted> acceptOffer(String entryId, String paymentOption) async => BookingStarted.fromJson(
      _map(await _api.post('/api/client/waitlist/$entryId/accept', body: {'payment_option': paymentOption})));

  Future<void> leaveWaitlist(String entryId) => _api.delete('/api/client/waitlist/$entryId');

  Future<void> writeReview(String bookingId, int rating, String? comment, {required bool editing}) {
    final body = {'rating': rating, if (comment != null && comment.isNotEmpty) 'comment': comment};
    return editing
        ? _api.patch('/api/client/bookings/$bookingId/review', body: body)
        : _api.post('/api/client/bookings/$bookingId/review', body: body);
  }

  Future<void> deleteMyData() => _api.post('/api/client/account/delete', body: {'confirm': 'DELETE'});
}

final accountApiProvider = Provider<AccountApi>((ref) => AccountApi(ref.watch(apiClientProvider)));
