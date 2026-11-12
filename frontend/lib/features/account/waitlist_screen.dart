import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../app/tokens.dart';
import '../../core/api/api_exception.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import '../booking/booking_flow_screen.dart' show goToCheckout;
import 'account_data.dart';

/// Times you're waiting for, and offers to book a freed time before someone else does.
class WaitlistScreen extends ConsumerWidget {
  const WaitlistScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ClientShell(
      child: PageScroll(maxWidth: 720, children: [
        const PageTitle('Waitlist', subtitle: 'If someone cancels a time you wanted, it’s offered here. The first person to book it gets it.'),
        AsyncView<List<WaitlistItem>>(
          value: ref.watch(waitlistProvider),
          onRetry: () => ref.invalidate(waitlistProvider),
          data: (items) {
            if (items.isEmpty) {
              return const EmptyState(
                icon: Icons.notifications_none_rounded,
                title: 'You’re not waiting for anything',
                message: 'When a place is fully booked, tap “Tell me if a time opens” while booking.',
              );
            }
            return Column(children: [for (final item in items) _Entry(item: item)]);
          },
        ),
      ]),
    );
  }
}

class _Entry extends ConsumerStatefulWidget {
  const _Entry({required this.item});

  final WaitlistItem item;

  @override
  ConsumerState<_Entry> createState() => _EntryState();
}

class _EntryState extends ConsumerState<_Entry> {
  bool _busy = false;

  Future<void> _accept() async {
    final option = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('How would you like to hold it?'),
        children: [
          SimpleDialogOption(
            onPressed: () => Navigator.of(context).pop('deposit_held'),
            child: const Text('Keep a deposit aside (the rest when you come)'),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.of(context).pop('full_held'),
            child: const Text('Keep the full amount aside'),
          ),
        ],
      ),
    );
    if (option == null) return;
    setState(() => _busy = true);
    try {
      final started = await ref.read(accountApiProvider).acceptOffer(widget.item.id, option);
      if (mounted) goToCheckout(context, widget.item.businessSlug, started);
    } on ApiException catch (problem) {
      ref.invalidate(waitlistProvider);
      if (mounted) showMessage(context, problem.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _leave() async {
    setState(() => _busy = true);
    try {
      await ref.read(accountApiProvider).leaveWaitlist(widget.item.id);
      ref.invalidate(waitlistProvider);
    } on ApiException catch (problem) {
      if (mounted) showMessage(context, problem.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _clock(String time) {
    final parts = time.split(':');
    final hour = int.tryParse(parts.first) ?? 0;
    final minute = parts.length > 1 ? parts[1] : '00';
    final suffix = hour < 12 ? 'AM' : 'PM';
    final twelve = hour % 12 == 0 ? 12 : hour % 12;
    return minute == '00' ? '$twelve $suffix' : '$twelve:$minute $suffix';
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final item = widget.item;
    final day = DateFormat('EEEE d MMMM').format(item.wantedDate);
    final left = item.offerExpiresAt?.difference(DateTime.now());
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.md),
      child: Panel(
        color: item.isOffer ? Palette.heldBg : null,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(item.businessName, style: text.titleMedium)),
            if (item.isOffer)
              const StatusPill('A time opened up', state: MoneyState.held)
            else if (item.status == 'waiting')
              const StatusPill('Waiting', state: MoneyState.waiting)
            else
              StatusPill(item.status == 'booked' ? 'Booked' : 'Ended', state: MoneyState.charged),
          ]),
          const SizedBox(height: 4),
          Text('${item.visit}, $day, between ${_clock(item.earliest)} and ${_clock(item.latest)}', style: text.bodySmall),
          if (item.isOffer && item.offeredStartsAt != null) ...[
            const SizedBox(height: Space.md),
            Text(DateFormat('EEE d MMM, h:mm a').format(item.offeredStartsAt!.toLocal()), style: text.headlineSmall),
            if (left != null && !left.isNegative)
              Text('Offer ends in ${left.inMinutes} min', style: text.bodySmall?.copyWith(color: Palette.held)),
          ],
          if (item.isActive) ...[
            const SizedBox(height: Space.md),
            Wrap(spacing: Space.md, runSpacing: Space.sm, children: [
              if (item.isOffer) FilledButton(onPressed: _busy ? null : _accept, child: const Text('Book it')),
              TextButton(onPressed: _busy ? null : _leave, child: Text(item.isOffer ? 'Not this time' : 'Stop waiting')),
              if (!item.isOffer)
                TextButton(onPressed: () => context.go('/b/${item.businessSlug}'), child: const Text('See the business')),
            ]),
          ],
        ]),
      ),
    );
  }
}
