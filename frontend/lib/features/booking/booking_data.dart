import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';

// ---------- what the backend sends ----------

class StaffChoice {
  const StaffChoice({required this.id, required this.name});

  final String id;
  final String name;

  factory StaffChoice.fromJson(Map<String, dynamic> json) => StaffChoice(
      id: json['id'].toString(), name: json['name'] as String? ?? 'Staff');
}

/// One bookable start time. [raw] is the exact text the backend sent, sent back unchanged when booking.
class TimeSlot {
  const TimeSlot(
      {required this.raw,
      required this.startsAt,
      required this.endsAt,
      required this.staff});

  final String raw;
  final DateTime startsAt;
  final DateTime endsAt;
  final List<StaffChoice>
      staff; // who is free then; the first is the suggestion

  factory TimeSlot.fromJson(Map<String, dynamic> json) => TimeSlot(
        raw: json['starts_at'] as String,
        startsAt: DateTime.parse(json['starts_at'] as String),
        endsAt: DateTime.parse(json['ends_at'] as String),
        staff: [
          for (final item in (json['staff'] as List? ?? const []))
            StaffChoice.fromJson(Map<String, dynamic>.from(item as Map)),
        ],
      );
}

class NoticeLine {
  const NoticeLine({required this.label, required this.amount});

  final String label;
  final String amount; // already formatted by the backend, e.g. "₹80.00"
}

/// The deposit notice, written by the backend from the real amounts and policy.
class DepositNotice {
  const DepositNotice({
    required this.title,
    required this.summary,
    required this.lines,
    required this.policy,
    required this.paymentOption,
    this.ownerNote,
  });

  final String title;
  final String summary;
  final List<NoticeLine> lines;
  final List<String> policy;
  final String paymentOption;
  final String? ownerNote;

  factory DepositNotice.fromJson(Map<String, dynamic> json) => DepositNotice(
        title: json['title'] as String? ?? 'Before you book',
        summary: json['summary'] as String? ?? '',
        lines: [
          for (final item in (json['lines'] as List? ?? const []))
            NoticeLine(
                label: (item as Map)['label'].toString(),
                amount: item['amount'].toString()),
        ],
        policy: [
          for (final line in (json['policy'] as List? ?? const []))
            line.toString()
        ],
        paymentOption: json['payment_option'] as String? ?? 'deposit_held',
        ownerNote: json['owner_note'] as String?,
      );
}

class Availability {
  const Availability({
    required this.durationMinutes,
    required this.price,
    required this.deposit,
    required this.totalPrice,
    required this.taxAmount,
    required this.pricesIncludeTax,
    required this.currency,
    required this.paymentOptions,
    required this.notice,
    required this.showNoticeBeforeTimes,
    required this.staffChoices,
    required this.times,
    this.taxLabel,
  });

  final int durationMinutes;
  final String price;
  final String deposit;
  final String
      totalPrice; // what the client pays for the whole visit, tax included
  final String?
      taxLabel; // e.g. "GST"; null when the business doesn't charge tax
  final String taxAmount;
  final bool pricesIncludeTax;
  final String currency;
  final List<String> paymentOptions;
  final DepositNotice notice;
  final bool showNoticeBeforeTimes;
  final List<StaffChoice> staffChoices;
  final List<TimeSlot> times;

  bool get offersDeposit => paymentOptions.contains('deposit_held');
  bool get offersFull => paymentOptions.contains('full_held');

  factory Availability.fromJson(Map<String, dynamic> json) => Availability(
        durationMinutes: (json['duration_minutes'] as num).toInt(),
        price: json['price'].toString(),
        deposit: json['deposit'].toString(),
        totalPrice: (json['total_price'] ?? json['price']).toString(),
        taxLabel: json['tax_label'] as String?,
        taxAmount: (json['tax_amount'] ?? '0').toString(),
        pricesIncludeTax: json['prices_include_tax'] as bool? ?? true,
        currency: json['currency'] as String? ?? 'USD',
        paymentOptions: [
          for (final option in (json['payment_options'] as List? ?? const []))
            option.toString()
        ],
        notice: DepositNotice.fromJson(Map<String, dynamic>.from(
            json['deposit_notice'] as Map? ?? const {})),
        showNoticeBeforeTimes:
            json['show_notice_before_times'] as bool? ?? true,
        staffChoices: [
          for (final item in (json['staff_choices'] as List? ?? const []))
            StaffChoice.fromJson(Map<String, dynamic>.from(item as Map)),
        ],
        times: [
          for (final item in (json['times'] as List? ?? const []))
            TimeSlot.fromJson(Map<String, dynamic>.from(item as Map)),
        ],
      );
}

class ClassSession {
  const ClassSession(
      {required this.id,
      required this.startsAt,
      required this.endsAt,
      required this.seatsLeft});

  final String id;
  final DateTime startsAt;
  final DateTime endsAt;
  final int seatsLeft;

  factory ClassSession.fromJson(Map<String, dynamic> json) => ClassSession(
        id: json['id'].toString(),
        startsAt: DateTime.parse(json['starts_at'] as String),
        endsAt: DateTime.parse(json['ends_at'] as String),
        seatsLeft: (json['seats_left'] as num?)?.toInt() ?? 0,
      );
}

class BookingStarted {
  const BookingStarted({
    required this.bookingId,
    required this.heldAmount,
    required this.currency,
    required this.paymentExpiresAt,
    required this.checkoutUrl,
  });

  final String bookingId;
  final String heldAmount;
  final String currency;
  final DateTime paymentExpiresAt;
  final String checkoutUrl;

  factory BookingStarted.fromJson(Map<String, dynamic> json) => BookingStarted(
        bookingId: json['booking_id'].toString(),
        heldAmount: json['held_amount'].toString(),
        currency: json['currency'] as String? ?? 'USD',
        paymentExpiresAt: DateTime.parse(json['payment_expires_at'] as String),
        checkoutUrl: json['checkout_url'] as String,
      );
}

/// A client's booking, as the backend reports it (used while waiting for PayPal, and on the confirmation).
class ClientBooking {
  const ClientBooking({
    required this.id,
    required this.status,
    required this.businessName,
    required this.serviceName,
    required this.startsAt,
    required this.endsAt,
    required this.timezone,
    required this.price,
    required this.heldAmount,
    required this.currency,
    required this.paymentOption,
    this.staffName,
    this.confirmationNumber,
    this.items = const [],
    this.checkInToken,
    this.attendeeName,
  });

  final String id;
  final String
      status; // pending_payment, confirmed, expired, cancelled, attended, no_show
  final String businessName;
  final String serviceName; // "Haircut + Hair wash"
  final String? staffName;
  final DateTime startsAt;
  final DateTime endsAt;
  final String timezone;
  final String price;
  final String heldAmount;
  final String currency;
  final String paymentOption;
  final String? confirmationNumber;
  final List<BookingItem> items;
  final String?
      checkInToken; // shown as a QR code for the business to scan at check-in
  final String? attendeeName;

  bool get isPending => status == 'pending_payment';
  bool get isConfirmed => status == 'confirmed';

  factory ClientBooking.fromJson(Map<String, dynamic> json) => ClientBooking(
        id: json['id'].toString(),
        status: json['status'] as String? ?? 'pending_payment',
        businessName: json['business_name'] as String? ?? '',
        serviceName: json['service_name'] as String? ?? '',
        staffName: json['staff_name'] as String?,
        startsAt: DateTime.parse(json['starts_at'] as String),
        endsAt: DateTime.parse(json['ends_at'] as String),
        timezone: json['timezone'] as String? ?? 'UTC',
        price: json['price'].toString(),
        heldAmount: json['held_amount'].toString(),
        currency: json['currency'] as String? ?? 'USD',
        paymentOption: json['payment_option'] as String? ?? 'deposit_held',
        confirmationNumber: json['confirmation_number'] as String?,
        items: [
          for (final item in (json['items'] as List? ?? const []))
            BookingItem.fromJson(Map<String, dynamic>.from(item as Map)),
        ],
        checkInToken: json['check_in_token'] as String?,
        attendeeName: json['attendee_name'] as String?,
      );
}

class BookingItem {
  const BookingItem(
      {required this.name,
      required this.kind,
      required this.durationMinutes,
      required this.price});

  final String name;
  final String kind;
  final int durationMinutes;
  final String price;

  factory BookingItem.fromJson(Map<String, dynamic> json) => BookingItem(
        name: json['name'] as String? ?? '',
        kind: json['kind'] as String? ?? 'main',
        durationMinutes: (json['duration_minutes'] as num?)?.toInt() ?? 0,
        price: (json['price'] ?? '0').toString(),
      );
}

// ---------- reading ----------

/// Which services, and optionally which staff member. Service IDs are joined with commas so equal requests match.
typedef AvailabilityKey = ({String slug, String serviceIds, String? staffId});

final availabilityProvider = FutureProvider.autoDispose
    .family<Availability, AvailabilityKey>((ref, key) async {
  final json = await ref.watch(apiClientProvider).post(
    '/api/public/businesses/${Uri.encodeComponent(key.slug)}/availability',
    body: {
      'service_ids': key.serviceIds.split(','),
      if (key.staffId != null) 'staff_id': key.staffId,
    },
  );
  return Availability.fromJson(Map<String, dynamic>.from(json as Map));
});

typedef SessionsKey = ({String slug, String serviceId});

final classSessionsProvider = FutureProvider.autoDispose
    .family<List<ClassSession>, SessionsKey>((ref, key) async {
  final json = await ref.watch(apiClientProvider).get(
      '/api/public/businesses/${Uri.encodeComponent(key.slug)}/services/${key.serviceId}/slots');
  return [
    for (final item in json as List)
      ClassSession.fromJson(Map<String, dynamic>.from(item as Map))
  ];
});

// ---------- doing ----------

class BookingApi {
  const BookingApi(this._api);

  final ApiClient _api;

  /// A client needs a name on file before their first booking (the phone comes from their sign-in).
  Future<bool> hasProfile() async {
    try {
      await _api.get('/api/client/profile');
      return true;
    } on ApiException catch (problem) {
      if (problem.isNotFound || problem.isConflict) return false;
      rethrow;
    }
  }

  Future<void> saveName(String name) =>
      _api.put('/api/client/profile', body: {'name': name});

  Future<BookingStarted> startAppointment({
    required List<String> serviceIds,
    required String startsAt,
    required String paymentOption,
    required String name,
    required String email,
    String? staffId,
    String? attendeeName,
  }) async {
    final json = await _api.post('/api/client/bookings', body: {
      'service_ids': serviceIds,
      'starts_at': startsAt,
      'payment_option': paymentOption,
      'name': name,
      'email': email,
      if (staffId != null) 'staff_id': staffId,
      if (attendeeName != null && attendeeName.isNotEmpty)
        'attendee_name': attendeeName,
    });
    return BookingStarted.fromJson(Map<String, dynamic>.from(json as Map));
  }

  Future<BookingStarted> startClass({
    required String slotId,
    required String paymentOption,
    required String name,
    required String email,
    String? attendeeName,
  }) async {
    final json = await _api.post('/api/client/bookings/class', body: {
      'slot_id': slotId,
      'payment_option': paymentOption,
      'name': name,
      'email': email,
      if (attendeeName != null && attendeeName.isNotEmpty)
        'attendee_name': attendeeName,
    });
    return BookingStarted.fromJson(Map<String, dynamic>.from(json as Map));
  }

  Future<ClientBooking> booking(String id) async {
    final json = await _api.get('/api/client/bookings/$id');
    return ClientBooking.fromJson(Map<String, dynamic>.from(json as Map));
  }

  /// "Tell me if a time opens": services + a day + a window (local times "HH:mm"), or a full class session.
  Future<void> joinWaitlist({
    List<String>? serviceIds,
    String? wantedDate,
    String? earliest,
    String? latest,
    String? slotId,
  }) =>
      _api.post('/api/client/waitlist',
          body: slotId != null
              ? {'slot_id': slotId}
              : {
                  'service_ids': serviceIds,
                  'wanted_date': wantedDate,
                  'earliest_time': earliest,
                  'latest_time': latest
                });
}

final bookingApiProvider =
    Provider<BookingApi>((ref) => BookingApi(ref.watch(apiClientProvider)));
