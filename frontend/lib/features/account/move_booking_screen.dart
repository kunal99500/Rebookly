import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../app/tokens.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/time.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../booking/booking_data.dart';
import 'account_data.dart';

/// Move a booking: only times it can really move to are shown. Same services, same deposit, same rules.
class MoveBookingScreen extends ConsumerWidget {
  const MoveBookingScreen({super.key, required this.bookingId});

  final String bookingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) => ClientShell(
        child: AsyncView<ClientBooking>(
          value: ref.watch(bookingDetailProvider(bookingId)),
          page: true,
          onRetry: () => ref.invalidate(bookingDetailProvider(bookingId)),
          data: (booking) => _Mover(booking: booking),
        ),
      );
}

class _Mover extends ConsumerStatefulWidget {
  const _Mover({required this.booking});

  final ClientBooking booking;

  @override
  ConsumerState<_Mover> createState() => _MoverState();
}

class _MoverState extends ConsumerState<_Mover> {
  int _day = 0;
  Future<List<MoveOption>>? _options;
  bool _busy = false;

  List<DateTime> get _days {
    final today = inZone(DateTime.now(), widget.booking.timezone);
    return [for (var i = 0; i < 3; i++) DateTime(today.year, today.month, today.day + i)];
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    _options = ref.read(accountApiProvider).moveOptions(widget.booking.id, isoDate(_days[_day]));
  }

  Future<void> _move(MoveOption option) async {
    final when = formatDayTime(option.startsAt, widget.booking.timezone);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Move your booking?'),
        content: Text('To $when. Same services, same deposit and the same cancellation rules. You’ll get a new confirmation.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Back')),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Move it')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      await ref.read(accountApiProvider).move(widget.booking.id, option.raw);
      ref.invalidate(bookingDetailProvider(widget.booking.id));
      ref.invalidate(myBookingsProvider);
      if (!mounted) return;
      showMessage(context, 'Moved to $when.');
      context.go('/my/bookings/${widget.booking.id}');
    } on ApiException catch (problem) {
      if (mounted) {
        showMessage(context, problem.message);
        setState(_load);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final booking = widget.booking;
    final days = _days;
    return PageScroll(maxWidth: 720, children: [
      TextButton.icon(
        onPressed: () => context.go('/my/bookings/${booking.id}'),
        icon: const Icon(Icons.arrow_back_rounded, size: 18),
        label: const Text('Back to booking'),
      ),
      const SizedBox(height: Space.sm),
      Text('Move to another time', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text(
        '${booking.serviceName} at ${booking.businessName}, now ${formatDayTime(booking.startsAt, booking.timezone)}.',
        style: text.bodyLarge?.copyWith(color: Palette.muted),
      ),
      const SizedBox(height: Space.xl),
      Wrap(spacing: Space.sm, children: [
        for (var i = 0; i < days.length; i++)
          ChoiceChip(
            label: Text(i == 0 ? 'Today' : (i == 1 ? 'Tomorrow' : DateFormat('EEE d MMM').format(days[i]))),
            selected: _day == i,
            showCheckmark: false,
            onSelected: (_) => setState(() {
              _day = i;
              _load();
            }),
          ),
      ]),
      const SizedBox(height: Space.xl),
      FutureBuilder<List<MoveOption>>(
        future: _options,
        builder: (context, snapshot) {
          if (snapshot.hasError) return ErrorPanel(error: snapshot.error!, onRetry: () => setState(_load));
          if (!snapshot.hasData) return const SkeletonList(rows: 2);
          final options = snapshot.data!;
          if (options.isEmpty) {
            return const EmptyState(
              icon: Icons.event_busy_outlined,
              title: 'No free times that day',
              message: 'Try another day. Bookings can be moved until shortly before the free-cancellation time.',
            );
          }
          return Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
            for (final option in options)
              SizedBox(
                width: 104,
                child: OutlinedButton(
                  onPressed: _busy ? null : () => _move(option),
                  style: OutlinedButton.styleFrom(minimumSize: const Size(0, 48), padding: EdgeInsets.zero, backgroundColor: Palette.surface),
                  child: Text(formatTime(option.startsAt, booking.timezone)),
                ),
              ),
          ]);
        },
      ),
    ]);
  }
}
