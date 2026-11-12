import 'package:flutter_test/flutter_test.dart';
import 'package:rebookly_frontend/features/account/account_data.dart';
import 'package:rebookly_frontend/features/account/booking_status.dart';
import 'package:rebookly_frontend/features/booking/booking_data.dart';
import 'package:rebookly_frontend/shared/money_state.dart';

ClientBooking _booking(String status, DateTime start) => ClientBooking.fromJson({
      'id': 'b1',
      'status': status,
      'business_name': 'Ravi’s',
      'service_name': 'Haircut',
      'starts_at': start.toIso8601String(),
      'ends_at': start.add(const Duration(minutes: 30)).toIso8601String(),
      'timezone': 'Asia/Kolkata',
      'price': '300.00',
      'held_amount': '80.00',
      'currency': 'INR',
      'payment_option': 'deposit_held',
      'check_in_token': 'abc',
      'items': [
        {'name': 'Haircut', 'kind': 'main', 'duration_minutes': 30, 'price': '300.00'},
      ],
    });

void main() {
  final now = DateTime.utc(2026, 11, 12, 10);

  test('statuses read in plain words with the right money colour', () {
    expect(bookingStatus(_booking('confirmed', now.add(const Duration(days: 1))), now).state, MoneyState.held);
    expect(bookingStatus(_booking('attended', now), now).label, 'Visited');
    expect(bookingStatus(_booking('no_show', now), now).state, MoneyState.problem);
    expect(isUpcoming(_booking('confirmed', now.add(const Duration(hours: 2))), now), isTrue);
    expect(isUpcoming(_booking('cancelled', now.add(const Duration(hours: 2))), now), isFalse);
  });

  test('bookings keep their items and check-in code', () {
    final booking = _booking('confirmed', now);
    expect(booking.items.single.name, 'Haircut');
    expect(booking.checkInToken, 'abc');
  });

  test('a free cancellation is recognised', () {
    final free = CancelPreview.fromJson({'fee': '0.00', 'released': '80.00', 'currency': 'INR', 'reason': 'Free', 'needs_owner_approval': false});
    final late = CancelPreview.fromJson({'fee': '40.00', 'released': '40.00', 'currency': 'INR', 'reason': 'Late', 'needs_owner_approval': true});
    expect(free.isFree, isTrue);
    expect(late.isFree, isFalse);
  });

  test('documents link to the backend page', () {
    final link = DocumentLink.fromJson({'type': 'fee_receipt', 'token': 't0k3n', 'number': 'RB-R-0001'})!;
    expect(link.title, 'Fee receipt');
    expect(link.url, endsWith('/api/public/documents/t0k3n'));
  });

  test('waitlist offers are recognised', () {
    final offer = WaitlistItem.fromJson({
      'id': 'w1', 'business_name': 'Ravi’s', 'business_slug': 'ravis', 'visit': 'Haircut',
      'wanted_date': '2026-11-13', 'earliest_time': '16:00:00', 'latest_time': '19:00:00', 'status': 'offered',
      'offered_starts_at': '2026-11-13T11:00:00Z', 'offer_expires_at': '2026-11-13T05:30:00Z',
    });
    expect(offer.isOffer && offer.isActive, isTrue);
  });
}
