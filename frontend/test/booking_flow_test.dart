import 'package:flutter_test/flutter_test.dart';
import 'package:rebookly_frontend/features/booking/booking_data.dart';
import 'package:rebookly_frontend/features/booking/flow_state.dart';
import 'package:rebookly_frontend/shared/hold_ticket.dart';

void main() {
  group('the booking flow lives in the address', () {
    test('a full selection survives a round trip through the address', () {
      const state = FlowState(serviceIds: ['a', 'b'], staffFilter: 'anna', time: '2026-11-18T11:00:00+00:00', staffId: 'anna', pay: 'full_held');
      final back = FlowState.fromQuery(state.toQuery());
      expect(back.serviceIds, ['a', 'b']);
      expect(back.time, '2026-11-18T11:00:00+00:00');
      expect((back.staffFilter, back.staffId, back.pay), ('anna', 'anna', 'full_held'));
    });

    test('each step forgets what no longer applies', () {
      const state = FlowState(serviceIds: ['a'], time: 't', staffId: 's', pay: 'full_held');
      expect(state.backToTimes().time, isNull);
      expect(state.withStaffFilter('ben').time, isNull);
      expect(state.editServices().editing, isTrue);
      expect(state.editServices().serviceIds, ['a']);
    });

    test('an empty address starts at choosing services', () {
      final state = FlowState.fromQuery(const {});
      expect(state.serviceIds, isEmpty);
      expect(state.isClass, isFalse);
    });
  });

  group('cancellation sentences become ticks and crosses', () {
    test('free things get a tick', () {
      expect(TicketRule.fromNotice('Free cancellation up to 24 hours before.').free, isTrue);
      expect(TicketRule.fromNotice('No fee for not showing up.').free, isTrue);
      expect(TicketRule.fromNotice('Late cancellations are free too.').free, isTrue);
    });

    test('things that may cost get a cross', () {
      expect(TicketRule.fromNotice('Late cancellation keeps ₹40.00.').free, isFalse);
      expect(TicketRule.fromNotice('Not showing up keeps ₹80.00.').free, isFalse);
    });
  });

  test('availability is read from the backend exactly', () {
    final availability = Availability.fromJson({
      'duration_minutes': 45,
      'price': '450.00',
      'deposit': '80.00',
      'total_price': '450.00',
      'tax_label': null,
      'tax_amount': '0.00',
      'prices_include_tax': true,
      'currency': 'INR',
      'payment_options': ['deposit_held', 'full_held'],
      'deposit_notice': {
        'title': 'Before you book',
        'summary': '₹80.00 will be held on your card or PayPal. It isn’t charged now.',
        'lines': [
          {'label': 'Held now (not charged)', 'amount': '₹80.00'},
          {'label': 'Pay at the business', 'amount': '₹370.00'},
        ],
        'policy': ['Free cancellation up to 24 hours before.'],
        'owner_note': 'Please arrive 5 minutes early.',
        'payment_option': 'deposit_held',
      },
      'show_notice_before_times': true,
      'staff_choices': [{'id': 's1', 'name': 'Anna'}],
      'times': [
        {'starts_at': '2026-11-18T11:00:00Z', 'ends_at': '2026-11-18T11:45:00Z', 'staff': [{'id': 's1', 'name': 'Anna'}]},
      ],
    });
    expect(availability.offersDeposit && availability.offersFull, isTrue);
    expect(availability.notice.lines.last.amount, '₹370.00');
    expect(availability.times.single.raw, '2026-11-18T11:00:00Z');   // sent back unchanged when booking
    expect(availability.times.single.staff.single.name, 'Anna');
  });
}
