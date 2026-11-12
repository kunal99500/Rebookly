import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/format/money.dart';
import '../../core/format/time.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import '../booking/booking_data.dart';
import 'account_data.dart';
import 'booking_status.dart';

/// My bookings: what's coming up (with what's kept aside), then past visits.
class MyBookingsScreen extends ConsumerWidget {
  const MyBookingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bookings = ref.watch(myBookingsProvider);
    final offers = ref.watch(waitlistProvider).valueOrNull?.where((w) => w.isOffer).toList() ?? const [];
    final text = Theme.of(context).textTheme;
    return ClientShell(
      child: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(myBookingsProvider);
          ref.invalidate(waitlistProvider);
        },
        child: PageScroll(maxWidth: 760, children: [
          PageTitle(
            'My bookings',
            action: IconButton(
              tooltip: 'Refresh',
              icon: const Icon(Icons.refresh_rounded),
              onPressed: () {
                ref.invalidate(myBookingsProvider);
                ref.invalidate(waitlistProvider);
              },
            ),
          ),
          if (offers.isNotEmpty) ...[
            _OfferBanner(count: offers.length),
            const SizedBox(height: Space.xl),
          ],
          AsyncView<List<ClientBooking>>(
            value: bookings,
            onRetry: () => ref.invalidate(myBookingsProvider),
            data: (list) {
              final now = DateTime.now();
              final upcoming = list.where((b) => isUpcoming(b, now)).toList()..sort((a, b) => a.startsAt.compareTo(b.startsAt));
              final past = list.where((b) => !isUpcoming(b, now)).toList()..sort((a, b) => b.startsAt.compareTo(a.startsAt));
              if (list.isEmpty) {
                return EmptyState(
                  icon: Icons.event_available_outlined,
                  title: 'No bookings yet',
                  message: 'When you book a barber, salon, tutor or trainer, it shows up here with what’s kept aside.',
                  action: FilledButton(onPressed: () => context.go('/search'), child: const Text('Find a place')),
                );
              }
              return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Coming up', style: text.headlineSmall),
                const SizedBox(height: Space.md),
                if (upcoming.isEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: Space.lg),
                    child: Text('Nothing booked right now.', style: text.bodyLarge?.copyWith(color: Palette.muted)),
                  ),
                for (final booking in upcoming) _BookingCard(booking: booking, now: now, prominent: true),
                if (past.isNotEmpty) ...[
                  const SizedBox(height: Space.xl),
                  Text('Past', style: text.headlineSmall),
                  const SizedBox(height: Space.md),
                  for (final booking in past) _BookingCard(booking: booking, now: now),
                ],
              ]);
            },
          ),
        ]),
      ),
    );
  }
}

class _OfferBanner extends StatelessWidget {
  const _OfferBanner({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Material(
      color: Palette.heldBg,
      borderRadius: BorderRadius.circular(Radii.card),
      child: InkWell(
        borderRadius: BorderRadius.circular(Radii.card),
        onTap: () => context.go('/my/waitlist'),
        child: Padding(
          padding: const EdgeInsets.all(Space.lg),
          child: Row(children: [
            const Icon(Icons.notifications_active_rounded, color: Palette.held),
            const SizedBox(width: Space.md),
            Expanded(
              child: Text(
                count == 1 ? 'A time you wanted just opened up' : '$count times you wanted just opened up',
                style: text.titleSmall?.copyWith(color: Palette.held),
              ),
            ),
            Text('Book it', style: text.labelLarge?.copyWith(color: Palette.held)),
            const Icon(Icons.chevron_right_rounded, color: Palette.held),
          ]),
        ),
      ),
    );
  }
}

class _BookingCard extends StatelessWidget {
  const _BookingCard({required this.booking, required this.now, this.prominent = false});

  final ClientBooking booking;
  final DateTime now;
  final bool prominent;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final status = bookingStatus(booking, now);
    final local = inZone(booking.startsAt, booking.timezone);
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
      child: Material(
        color: Palette.surface,
        borderRadius: BorderRadius.circular(Radii.card),
        child: InkWell(
          borderRadius: BorderRadius.circular(Radii.card),
          onTap: () => context.go('/my/bookings/${booking.id}'),
          child: Container(
            padding: const EdgeInsets.all(Space.lg),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(Radii.card),
              border: Border.all(color: Palette.line),
            ),
            child: Row(children: [
              Container(
                width: 56,
                padding: const EdgeInsets.symmetric(vertical: 8),
                decoration: BoxDecoration(
                  color: prominent ? Palette.sage : Palette.paper,
                  borderRadius: BorderRadius.circular(Radii.control),
                ),
                child: Column(children: [
                  Text(formatDayShort(local), style: text.labelSmall?.copyWith(color: Palette.muted)),
                  Text('${local.day}', style: text.headlineSmall?.copyWith(color: prominent ? Palette.forest : Palette.ink)),
                ]),
              ),
              const SizedBox(width: Space.lg),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(booking.serviceName, style: text.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
                  Text(
                    '${booking.businessName}, ${formatTime(booking.startsAt, booking.timezone)}',
                    style: text.bodySmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: Space.sm),
                  StatusPill(status.label, state: status.state),
                ]),
              ),
              const SizedBox(width: Space.md),
              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                Text(formatMoney(booking.heldAmount, booking.currency),
                    style: text.titleMedium?.copyWith(fontFeatures: Fonts.tabular)),
                Text('kept aside', style: text.bodySmall),
              ]),
            ]),
          ),
        ),
      ),
    );
  }
}
