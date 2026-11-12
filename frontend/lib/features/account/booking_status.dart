import '../../shared/money_state.dart';
import '../booking/booking_data.dart';

/// How a booking's status reads to the client, with the matching money colour.
({String label, MoneyState state}) bookingStatus(ClientBooking booking, DateTime now) {
  switch (booking.status) {
    case 'confirmed':
      return booking.endsAt.isAfter(now)
          ? (label: 'Deposit kept aside', state: MoneyState.held)
          : (label: 'Waiting for check-in', state: MoneyState.waiting);
    case 'pending_payment':
      return (label: 'Waiting for payment', state: MoneyState.waiting);
    case 'attended':
      return (label: 'Visited', state: MoneyState.released);
    case 'cancelled':
      return (label: 'Cancelled', state: MoneyState.charged);
    case 'no_show':
      return (label: 'Missed', state: MoneyState.problem);
    default:
      return (label: 'Not completed', state: MoneyState.charged);
  }
}

bool isUpcoming(ClientBooking booking, DateTime now) =>
    (booking.status == 'confirmed' || booking.status == 'pending_payment') && booking.endsAt.isAfter(now);
