import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/format/money.dart';
import '../../core/format/time.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import '../settings/settings_common.dart';
import 'day_data.dart';
import 'owner_page.dart';

/// The owner's bookings, day by day: check clients in, mark no-shows, move or cancel.
class OwnerBookingsScreen extends StatelessWidget {
  const OwnerBookingsScreen({super.key});

  @override
  Widget build(BuildContext context) => OwnerPage(
        title: 'Bookings',
        actions: [
          FilledButton.icon(
            onPressed: () => context.go('/business/check-in'),
            icon: const Icon(Icons.qr_code_scanner_rounded, size: 20),
            label: const Text('Scan to check in'),
          ),
        ],
        builder: (context, id, business) => _Bookings(businessId: id, timezone: '${business['timezone'] ?? 'UTC'}'),
      );
}

class _Bookings extends ConsumerStatefulWidget {
  const _Bookings({required this.businessId, required this.timezone});

  final String businessId;
  final String timezone;

  @override
  ConsumerState<_Bookings> createState() => _BookingsState();
}

class _BookingsState extends ConsumerState<_Bookings> {
  int _offset = 0;   // days from today
  String? _staff;

  DateTime get _today {
    final now = inZone(DateTime.now(), widget.timezone);
    return DateTime(now.year, now.month, now.day);
  }

  DayKey get _key => (
        businessId: widget.businessId,
        startIso: localMidnightUtc(_today.add(Duration(days: _offset)), widget.timezone),
        days: 1,
      );

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final value = ref.watch(ownerBookingsProvider(_key));
    return PageScroll(maxWidth: 900, children: [
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(children: [
          for (var i = -1; i < 14; i++)
            Padding(
              padding: const EdgeInsets.only(right: Space.sm),
              child: ChoiceChip(
                label: Text(i == 0 ? 'Today' : (i == 1 ? 'Tomorrow' : (i == -1 ? 'Yesterday' : DateFormat('EEE d').format(_today.add(Duration(days: i)))))),
                selected: _offset == i,
                showCheckmark: false,
                onSelected: (_) => setState(() => _offset = i),
              ),
            ),
        ]),
      ),
      const SizedBox(height: Space.xl),
      AsyncView<List<OwnerBooking>>(
        value: value,
        onRetry: () => ref.invalidate(ownerBookingsProvider(_key)),
        data: (all) {
          final staffNames = {for (final b in all) if (b.staffName != null) b.staffName!}.toList()..sort();
          final list = all.where((b) => b.status != 'expired' && (_staff == null || b.staffName == _staff)).toList()
            ..sort((a, b) => a.startsAt.compareTo(b.startsAt));
          final day = _today.add(Duration(days: _offset));
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(DateFormat('EEEE d MMMM').format(day), style: text.headlineMedium)),
              Text('${list.where((b) => b.status != 'cancelled').length} bookings', style: text.bodySmall),
            ]),
            if (staffNames.length > 1) ...[
              const SizedBox(height: Space.md),
              Wrap(spacing: Space.sm, children: [
                ChoiceChip(label: const Text('Everyone'), selected: _staff == null, showCheckmark: false, onSelected: (_) => setState(() => _staff = null)),
                for (final name in staffNames)
                  ChoiceChip(label: Text(name), selected: _staff == name, showCheckmark: false, onSelected: (_) => setState(() => _staff = name)),
              ]),
            ],
            const SizedBox(height: Space.lg),
            if (list.isEmpty)
              const EmptyState(icon: Icons.event_available_outlined, title: 'Nothing booked', message: 'Bookings for this day will show here.'),
            for (final booking in list)
              _BookingRow(
                booking: booking,
                timezone: widget.timezone,
                onTap: () async {
                  final changed = await showModalBottomSheet<bool>(
                    context: context,
                    isScrollControlled: true,
                    backgroundColor: Palette.surface,
                    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.sheet))),
                    builder: (context) => BookingActions(businessId: widget.businessId, booking: booking, timezone: widget.timezone),
                  );
                  if (changed == true) ref.invalidate(ownerBookingsProvider(_key));
                },
              ),
          ]);
        },
      ),
    ]);
  }
}

({String label, MoneyState state}) ownerStatus(OwnerBooking b, DateTime now) {
  if (b.checkedIn) return (label: 'Checked in', state: MoneyState.released);
  return switch (b.status) {
    'confirmed' => now.isAfter(b.startsAt)
        ? (label: 'Not checked in yet', state: MoneyState.waiting)
        : (label: 'Deposit kept aside', state: MoneyState.held),
    'pending_payment' => (label: 'Paying now', state: MoneyState.waiting),
    'cancelled' => (label: 'Cancelled', state: MoneyState.charged),
    'no_show' => (label: 'No-show', state: MoneyState.problem),
    _ => (label: b.status, state: MoneyState.charged),
  };
}

class _BookingRow extends StatelessWidget {
  const _BookingRow({required this.booking, required this.timezone, required this.onTap});

  final OwnerBooking booking;
  final String timezone;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final status = ownerStatus(booking, DateTime.now());
    final faded = booking.status == 'cancelled';
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
      child: Opacity(
        opacity: faded ? 0.55 : 1,
        child: Material(
          color: Palette.surface,
          borderRadius: BorderRadius.circular(Radii.card),
          child: InkWell(
            borderRadius: BorderRadius.circular(Radii.card),
            onTap: onTap,
            child: Container(
              padding: const EdgeInsets.all(Space.lg),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(Radii.card), border: Border.all(color: Palette.line)),
              child: Row(children: [
                SizedBox(
                  width: 84,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(formatTime(booking.startsAt, timezone), style: text.titleMedium?.copyWith(fontFeatures: Fonts.tabular)),
                    Text(formatTime(booking.endsAt, timezone), style: text.bodySmall),
                  ]),
                ),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(booking.clientName, style: text.titleMedium),
                    Text([booking.serviceName, if (booking.staffName != null) 'with ${booking.staffName}'].join(', '),
                        style: text.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis),
                    const SizedBox(height: 6),
                    StatusPill(status.label, state: status.state),
                  ]),
                ),
                Text(formatMoney(booking.held, booking.currency), style: text.titleSmall?.copyWith(fontFeatures: Fonts.tabular)),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

/// What the owner can do with one booking.
class BookingActions extends ConsumerStatefulWidget {
  const BookingActions({super.key, required this.businessId, required this.booking, required this.timezone});

  final String businessId;
  final OwnerBooking booking;
  final String timezone;

  @override
  ConsumerState<BookingActions> createState() => _BookingActionsState();
}

class _BookingActionsState extends ConsumerState<BookingActions> {
  String get _base => '/api/owner/businesses/${widget.businessId}';

  Future<void> _do(Future<dynamic> Function() action, String done) async {
    final saved = await runSave(context, () async {
      await action();
    }, done: done);
    if (saved && mounted) Navigator.of(context).pop(true);
  }

  Future<bool> _sure(String title, String body, String yes, {bool danger = false}) async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(title),
          content: Text(body),
          actions: [
            TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Back')),
            FilledButton(
              style: danger ? FilledButton.styleFrom(backgroundColor: Palette.problem) : null,
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(yes),
            ),
          ],
        ),
      ) ??
      false;

  Future<void> _move() async {
    final picked = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => _MoveDialog(base: _base, booking: widget.booking, timezone: widget.timezone),
    );
    if (picked == null) return;
    await _do(() => ref.read(apiClientProvider).post('$_base/bookings/${widget.booking.id}/reschedule', body: picked),
        'Moved. The client has been told and can cancel free if it doesn’t suit.');
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final b = widget.booking;
    final api = ref.read(apiClientProvider);
    final open = b.isConfirmed && !b.checkedIn;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(b.clientName, style: text.headlineSmall),
          if (b.bookedBy != null) Text('Booked by ${b.bookedBy}', style: text.bodySmall),
          const SizedBox(height: Space.sm),
          Text('${b.serviceName}, ${formatDayTime(b.startsAt, widget.timezone)}${b.staffName == null ? '' : ' with ${b.staffName}'}', style: text.bodyMedium),
          Text([if (b.phone != null) 'Phone ${b.phone}', if (b.reference != null) 'Ref ${b.reference}'].join('   '), style: text.bodySmall),
          const SizedBox(height: Space.md),
          Text('${formatMoney(b.held, b.currency)} kept aside', style: text.titleMedium?.copyWith(color: Palette.held)),
          const SizedBox(height: Space.xl),
          if (open) ...[
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                icon: const Icon(Icons.how_to_reg_rounded, size: 20),
                label: const Text('Check in'),
                onPressed: () => _do(() => api.post('$_base/bookings/${b.id}/check-in'), 'Checked in. The deposit goes toward their bill.'),
              ),
            ),
            const SizedBox(height: Space.sm),
            Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
              OutlinedButton.icon(icon: const Icon(Icons.schedule_rounded, size: 20), label: const Text('Move'), onPressed: _move),
              OutlinedButton.icon(
                icon: const Icon(Icons.person_off_outlined, size: 20),
                label: const Text('Didn’t come'),
                onPressed: () async {
                  if (await _sure('Mark as a no-show?', 'The fee from your policy is worked out and waits for your approval in Approvals. Nothing is charged yet.', 'Mark no-show')) {
                    await _do(() => api.post('$_base/bookings/${b.id}/no-show'), 'Marked as a no-show. Decide on the fee in Approvals.');
                  }
                },
              ),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(foregroundColor: Palette.problem),
                icon: const Icon(Icons.event_busy_outlined, size: 20),
                label: const Text('Cancel'),
                onPressed: () async {
                  if (await _sure('Cancel this booking?', 'When you cancel, the client is told and everything kept aside is released. Nothing is charged.', 'Cancel booking', danger: true)) {
                    await _do(() => api.post('$_base/bookings/${b.id}/cancel', body: const {}), 'Cancelled. The client’s deposit was released.');
                  }
                },
              ),
            ]),
          ] else
            Text(
              b.checkedIn ? 'Checked in.' : 'Nothing to do for this booking.',
              style: text.bodyMedium?.copyWith(color: Palette.muted),
            ),
        ]),
      ),
    );
  }
}

class _MoveDialog extends ConsumerStatefulWidget {
  const _MoveDialog({required this.base, required this.booking, required this.timezone});

  final String base;
  final OwnerBooking booking;
  final String timezone;

  @override
  ConsumerState<_MoveDialog> createState() => _MoveDialogState();
}

class _MoveDialogState extends ConsumerState<_MoveDialog> {
  int _day = 0;
  late Future<List<Map<String, dynamic>>> _times = _load();

  Future<List<Map<String, dynamic>>> _load() async {
    final now = inZone(DateTime.now(), widget.timezone);
    final day = DateTime(now.year, now.month, now.day + _day);
    return asList(await ref.read(apiClientProvider).get('${widget.base}/bookings/${widget.booking.id}/reschedule-options',
        query: {'day': isoDate(day)}));
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Move to'),
        content: SizedBox(
          width: 440,
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Wrap(spacing: Space.sm, children: [
              for (var i = 0; i < 3; i++)
                ChoiceChip(
                  label: Text(['Today', 'Tomorrow', 'Day after'][i]),
                  selected: _day == i,
                  showCheckmark: false,
                  onSelected: (_) => setState(() {
                    _day = i;
                    _times = _load();
                  }),
                ),
            ]),
            const SizedBox(height: Space.md),
            FutureBuilder<List<Map<String, dynamic>>>(
              future: _times,
              builder: (context, snapshot) {
                if (snapshot.hasError) return ErrorPanel(error: snapshot.error!);
                if (!snapshot.hasData) return const SkeletonList(rows: 1);
                if (snapshot.data!.isEmpty) return const Text('No free times that day.');
                return Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
                  for (final option in snapshot.data!)
                    OutlinedButton(
                      onPressed: () => Navigator.of(context).pop({'starts_at': '${option['starts_at']}'}),
                      child: Text(formatTime(DateTime.parse('${option['starts_at']}'), widget.timezone)),
                    ),
                ]);
              },
            ),
          ]),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      );
}
