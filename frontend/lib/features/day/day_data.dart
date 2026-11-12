import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../settings/settings_common.dart';

/// A booking as the owner sees it. The client's phone is masked (•••• 3456).
class OwnerBooking {
  const OwnerBooking(this.json);

  final Map<String, dynamic> json;

  String get id => '${json['id']}';
  String get status => '${json['status']}';
  String get serviceName => '${json['service_name'] ?? ''}';
  DateTime get startsAt => DateTime.parse('${json['starts_at']}');
  DateTime get endsAt => DateTime.parse('${json['ends_at']}');
  String get clientName => '${json['attendee_name'] ?? json['client_name'] ?? 'Client'}';
  String? get bookedBy => json['attendee_name'] != null ? '${json['client_name']}' : null;
  String? get phone => json['client_phone'] as String?;
  String? get staffName => json['staff_name'] as String?;
  String get held => '${json['held_amount'] ?? '0'}';
  String get currency => '${json['currency'] ?? 'USD'}';
  String? get reference => json['confirmation_number'] as String?;
  bool get checkedIn => json['checked_in_at'] != null || status == 'attended';
  bool get isConfirmed => status == 'confirmed';
}

typedef DayKey = ({String businessId, String startIso, int days});

final ownerBookingsProvider = FutureProvider.autoDispose.family<List<OwnerBooking>, DayKey>((ref, key) async {
  final json = await ref.watch(apiClientProvider).get('/api/owner/businesses/${key.businessId}/bookings',
      query: {'start': key.startIso, 'days': key.days});
  return [for (final item in asList(json is Map ? json['bookings'] : json)) OwnerBooking(item)];
});

final decisionsProvider = FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>((ref, businessId) async {
  final json = await ref.watch(apiClientProvider).get('/api/owner/businesses/$businessId/decisions');
  return asList(json is Map ? json['decisions'] : json);
});

final slotsProvider = FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>((ref, businessId) async {
  final json = await ref.watch(apiClientProvider).get('/api/owner/businesses/$businessId/slots');
  return asList(json is Map ? json['slots'] : json);
});

final ownerReviewsProvider = FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, businessId) async {
  return asMap(await ref.watch(apiClientProvider).get('/api/owner/businesses/$businessId/reviews'));
});

final ownerServicesProvider = FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>((ref, businessId) async {
  return asList(await ref.watch(apiClientProvider).get('/api/owner/businesses/$businessId/services'));
});
