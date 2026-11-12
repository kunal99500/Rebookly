import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/tokens.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/money.dart';
import '../../core/format/time.dart';
import '../../shared/client_shell.dart';
import '../../shared/hold_ticket.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'booking_data.dart';

/// Paying the hold: PayPal opens in a new tab, and this page waits.
/// It checks the booking every few seconds and turns into the confirmation the moment the hold is placed.
/// The time is kept for the client until [until]; after that the booking expires and the time is released.
class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key, required this.bookingId, this.checkoutUrl, this.until, this.businessSlug});

  final String bookingId;
  final String? checkoutUrl;
  final DateTime? until;
  final String? businessSlug;

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  static const _checkEvery = Duration(seconds: 3);

  ClientBooking? _booking;
  String? _problem;
  Timer? _poll;
  Timer? _tick;
  bool _openedPayPal = false;

  @override
  void initState() {
    super.initState();
    _check();
    _poll = Timer.periodic(_checkEvery, (_) => _check());
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _poll?.cancel();
    _tick?.cancel();
    super.dispose();
  }

  Future<void> _check() async {
    try {
      final booking = await ref.read(bookingApiProvider).booking(widget.bookingId);
      if (!mounted) return;
      setState(() {
        _booking = booking;
        _problem = null;
      });
      if (!booking.isPending) {
        _poll?.cancel();
        _tick?.cancel();
      }
    } on ApiException catch (problem) {
      if (mounted) setState(() => _problem = problem.message);
    }
  }

  Future<void> _openPayPal() async {
    final url = widget.checkoutUrl;
    if (url == null) return;
    setState(() => _openedPayPal = true);
    await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
  }

  Duration? get _timeLeft {
    final until = widget.until;
    if (until == null) return null;
    final left = until.difference(DateTime.now());
    return left.isNegative ? Duration.zero : left;
  }

  @override
  Widget build(BuildContext context) {
    final booking = _booking;
    final Widget body;
    if (booking == null) {
      body = _problem == null ? const _Waiting() : _Message(icon: Icons.error_outline_rounded, title: _problem!);
    } else if (booking.isConfirmed) {
      body = _Confirmed(booking: booking);
    } else if (booking.isPending && (_timeLeft == null || _timeLeft! > Duration.zero)) {
      body = _Pay(
        booking: booking,
        timeLeft: _timeLeft,
        canOpen: widget.checkoutUrl != null,
        opened: _openedPayPal,
        onOpen: _openPayPal,
      );
    } else {
      body = _Message(
        icon: Icons.timer_off_outlined,
        title: 'This booking timed out',
        message: 'The hold wasn’t finished in time, so the time was released and nothing was taken. You can book again.',
        action: widget.businessSlug == null
            ? null
            : FilledButton(onPressed: () => context.go('/b/${widget.businessSlug}/book'), child: const Text('Book again')),
      );
    }
    return ClientShell(child: PageScroll(maxWidth: 680, children: [body]));
  }
}

class _Waiting extends StatelessWidget {
  const _Waiting();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 64),
        child: Center(child: CircularProgressIndicator()),
      );
}

class _Pay extends StatelessWidget {
  const _Pay({required this.booking, required this.timeLeft, required this.canOpen, required this.opened, required this.onOpen});

  final ClientBooking booking;
  final Duration? timeLeft;
  final bool canOpen;
  final bool opened;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final minutes = timeLeft?.inMinutes;
    final seconds = timeLeft == null ? null : (timeLeft!.inSeconds % 60).toString().padLeft(2, '0');
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(opened ? 'Finish on PayPal' : 'One last step', style: text.displaySmall),
      const SizedBox(height: Space.md),
      Text(
        opened
            ? 'Approve the hold in the PayPal tab. This page updates by itself as soon as it’s done.'
            : 'PayPal opens in a new tab. Approve the hold there, then come back: this page updates by itself.',
        style: text.bodyLarge?.copyWith(color: Palette.muted),
      ),
      const SizedBox(height: Space.xl),
      Panel(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(booking.serviceName, style: text.titleMedium),
          Text('${booking.businessName}, ${formatDayTime(booking.startsAt, booking.timezone)}', style: text.bodySmall),
          const SizedBox(height: Space.lg),
          Row(children: [
            const StatusPill('Kept aside, not taken', state: MoneyState.held),
            const Spacer(),
            Text(formatMoney(booking.heldAmount, booking.currency),
                style: text.headlineSmall?.copyWith(color: Palette.held, fontFeatures: Fonts.tabular)),
          ]),
        ]),
      ),
      const SizedBox(height: Space.xl),
      if (canOpen)
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: onOpen,
            icon: const Icon(Icons.open_in_new_rounded, size: 20),
            label: Text(opened ? 'Open PayPal again' : 'Continue to PayPal'),
          ),
        ),
      if (minutes != null) ...[
        const SizedBox(height: Space.md),
        Row(children: [
          const Icon(Icons.schedule_rounded, size: 18, color: Palette.muted),
          const SizedBox(width: Space.sm),
          Text('Your time is kept for $minutes:$seconds more', style: text.bodySmall?.copyWith(fontFeatures: Fonts.tabular)),
        ]),
      ],
      if (opened) ...[
        const SizedBox(height: Space.xl),
        const Row(children: [
          SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
          SizedBox(width: Space.md),
          Expanded(child: Text('Waiting for PayPal…')),
        ]),
      ],
    ]);
  }
}

class _Confirmed extends StatelessWidget {
  const _Confirmed({required this.booking});

  final ClientBooking booking;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Icon(Icons.check_circle_rounded, color: Palette.released, size: 40),
      const SizedBox(height: Space.md),
      Text('You’re booked', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text(
        booking.confirmationNumber == null ? 'See you soon.' : 'Your booking reference is ${booking.confirmationNumber}.',
        style: text.bodyLarge?.copyWith(color: Palette.muted),
      ),
      const SizedBox(height: Space.xl),
      DecoratedBox(
        decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.sheet)),
        child: Padding(
          padding: const EdgeInsets.all(Space.lg),
          child: HoldTicket(
            title: booking.serviceName,
            lines: [
              booking.businessName,
              '${formatDayTime(booking.startsAt, booking.timezone)}${booking.staffName == null ? '' : ' with ${booking.staffName}'}',
            ],
            held: formatMoney(booking.heldAmount, booking.currency),
            heldCaption: 'kept aside, not taken',
            footnote: 'You can cancel or move it from My bookings. You’ll always see what it costs first.',
          ),
        ),
      ),
      const SizedBox(height: Space.xl),
      Wrap(spacing: Space.md, runSpacing: Space.md, children: [
        FilledButton(onPressed: () => context.go('/my'), child: const Text('See my bookings')),
        OutlinedButton(onPressed: () => context.go('/my/profile'), child: const Text('Get reminders by email')),
      ]),
    ]);
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.icon, required this.title, this.message, this.action});

  final IconData icon;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: Palette.muted, size: 36),
      const SizedBox(height: Space.md),
      Text(title, style: text.headlineMedium),
      if (message != null) ...[
        const SizedBox(height: Space.sm),
        Text(message!, style: text.bodyLarge?.copyWith(color: Palette.muted)),
      ],
      if (action != null) ...[const SizedBox(height: Space.xl), action!],
    ]);
  }
}
