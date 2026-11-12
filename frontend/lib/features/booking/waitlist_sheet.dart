import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../app/tokens.dart';
import '../../core/api/api_exception.dart';
import '../../core/auth/auth_service.dart';
import '../../core/format/time.dart';
import '../business/business_data.dart';
import 'booking_data.dart';
import 'booking_widgets.dart';

/// "Tell me if a time opens": pick a day and a part of the day. If someone cancels, they're offered the time.
Future<void> showWaitlistSheet(
  BuildContext context,
  WidgetRef ref, {
  required BusinessPage business,
  required List<String> serviceIds,
}) async {
  if (!ref.read(authServiceProvider).isClientSignedIn) {
    final here = GoRouterState.of(context).uri.toString();
    context.go(Uri(path: '/signin', queryParameters: {'from': here}).toString());
    return;
  }
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Palette.surface,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.sheet))),
    builder: (context) => _WaitlistSheet(business: business, serviceIds: serviceIds),
  );
}

class _WaitlistSheet extends ConsumerStatefulWidget {
  const _WaitlistSheet({required this.business, required this.serviceIds});

  final BusinessPage business;
  final List<String> serviceIds;

  @override
  ConsumerState<_WaitlistSheet> createState() => _WaitlistSheetState();
}

class _WaitlistSheetState extends ConsumerState<_WaitlistSheet> {
  static const _windows = [
    (label: 'Morning', detail: '9 AM to 12 PM', from: '09:00', to: '12:00'),
    (label: 'Afternoon', detail: '12 to 5 PM', from: '12:00', to: '17:00'),
    (label: 'Evening', detail: '5 to 9 PM', from: '17:00', to: '21:00'),
    (label: 'Any time', detail: 'Whenever they’re open', from: '06:00', to: '23:00'),
  ];

  int _day = 0;
  int _window = 3;
  bool _busy = false;
  String? _error;
  bool _done = false;

  List<DateTime> get _days {
    final today = inZone(DateTime.now(), widget.business.timezone);
    return [for (var i = 0; i < 3; i++) DateTime(today.year, today.month, today.day + i)];
  }

  Future<void> _join() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final api = ref.read(bookingApiProvider);
      if (!await api.hasProfile()) {
        if (!mounted) return;
        final name = await askForName(context);
        if (name == null) return;
        await api.saveName(name);
      }
      final window = _windows[_window];
      await api.joinWaitlist(
        serviceIds: widget.serviceIds,
        wantedDate: DateFormat('yyyy-MM-dd').format(_days[_day]),
        earliest: window.from,
        latest: window.to,
      );
      if (mounted) setState(() => _done = true);
    } on ApiException catch (problem) {
      if (mounted) setState(() => _error = problem.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final days = _days;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(24, 12, 24, 24 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Center(
            child: Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: Space.xl),
              decoration: BoxDecoration(color: Palette.line, borderRadius: BorderRadius.circular(2)),
            ),
          ),
          if (_done) ...[
            const Icon(Icons.notifications_active_rounded, color: Palette.forest, size: 32),
            const SizedBox(height: Space.md),
            Text('You’re on the list', style: text.headlineSmall),
            const SizedBox(height: Space.sm),
            Text(
              'If a time opens, we’ll offer it to you straight away. You’ll find offers under My bookings, '
              'and by email if you’ve added one. The first person to book it gets it.',
              style: text.bodyLarge?.copyWith(color: Palette.muted),
            ),
            const SizedBox(height: Space.xl),
            SizedBox(
              width: double.infinity,
              child: FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Done')),
            ),
          ] else ...[
            Text('Tell me if a time opens', style: text.headlineSmall),
            const SizedBox(height: Space.sm),
            Text(
              'Choose when suits you. If someone cancels, you’ll be offered their time.',
              style: text.bodyMedium?.copyWith(color: Palette.muted),
            ),
            const SizedBox(height: Space.xl),
            Text('Which day?', style: text.titleSmall),
            const SizedBox(height: Space.sm),
            Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
              for (var i = 0; i < days.length; i++)
                ChoiceChip(
                  label: Text(i == 0 ? 'Today' : (i == 1 ? 'Tomorrow' : DateFormat('EEE d MMM').format(days[i]))),
                  selected: _day == i,
                  showCheckmark: false,
                  onSelected: (_) => setState(() => _day = i),
                ),
            ]),
            const SizedBox(height: Space.xl),
            Text('What time of day?', style: text.titleSmall),
            const SizedBox(height: Space.sm),
            Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
              for (var i = 0; i < _windows.length; i++)
                ChoiceChip(
                  label: Text(_windows[i].label),
                  tooltip: _windows[i].detail,
                  selected: _window == i,
                  showCheckmark: false,
                  onSelected: (_) => setState(() => _window = i),
                ),
            ]),
            const SizedBox(height: Space.sm),
            Text(_windows[_window].detail, style: text.bodySmall),
            if (_error != null) ...[
              const SizedBox(height: Space.lg),
              Text(_error!, style: text.bodyMedium?.copyWith(color: Palette.problem)),
            ],
            const SizedBox(height: Space.xl),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _busy ? null : _join,
                child: _busy
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
                    : const Text('Tell me if a time opens'),
              ),
            ),
          ],
        ]),
      ),
    );
  }
}
