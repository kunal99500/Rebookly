import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/format/money.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import '../settings/settings_common.dart';
import 'day_data.dart';
import 'owner_page.dart';

/// Fees waiting for the owner's decision (charge, lower or waive), and payments to retry.
class ApprovalsScreen extends StatelessWidget {
  const ApprovalsScreen({super.key});

  @override
  Widget build(BuildContext context) => OwnerPage(
        title: 'Approvals',
        builder: (context, id, business) => _Approvals(businessId: id, currency: '${business['currency'] ?? 'USD'}'),
      );
}

class _Approvals extends ConsumerWidget {
  const _Approvals({required this.businessId, required this.currency});

  final String businessId;
  final String currency;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return PageScroll(maxWidth: 820, children: [
      Text('Approvals', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text('Nothing is charged until you decide. You can never charge more than the client agreed to.',
          style: text.bodyLarge?.copyWith(color: Palette.muted)),
      const SizedBox(height: Space.xl),
      AsyncView<List<Map<String, dynamic>>>(
        value: ref.watch(decisionsProvider(businessId)),
        onRetry: () => ref.invalidate(decisionsProvider(businessId)),
        data: (decisions) {
          final waiting = decisions.where((d) => d['status'] == 'pending_approval').toList();
          final failed = decisions.where((d) => d['status'] == 'failed').toList();
          final done = decisions.where((d) => d['status'] != 'pending_approval' && d['status'] != 'failed').take(20).toList();
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (waiting.isEmpty && failed.isEmpty)
              const EmptyState(icon: Icons.task_alt_rounded, title: 'All caught up', message: 'Late cancellations and no-shows will wait here for you.'),
            for (final d in failed) _Decision(decision: d, businessId: businessId, currency: currency),
            for (final d in waiting) _Decision(decision: d, businessId: businessId, currency: currency),
            if (done.isNotEmpty) ...[
              const SizedBox(height: Space.xl),
              Text('Decided', style: text.headlineSmall),
              const SizedBox(height: Space.sm),
              for (final d in done)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${d['reason']}', style: text.bodyMedium, maxLines: 2, overflow: TextOverflow.ellipsis),
                  subtitle: Text(DateFormat('d MMM, h:mm a').format(DateTime.parse('${d['created_at']}').toLocal()), style: text.bodySmall),
                  trailing: Text(
                    d['action'] == 'capture' ? formatMoney(d['final_amount'] ?? d['amount'], currency) : 'Released',
                    style: text.titleSmall,
                  ),
                ),
            ],
          ]);
        },
      ),
    ]);
  }
}

class _Decision extends ConsumerWidget {
  const _Decision({required this.decision, required this.businessId, required this.currency});

  final Map<String, dynamic> decision;
  final String businessId;
  final String currency;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final api = ref.read(apiClientProvider);
    final base = '/api/owner/businesses/$businessId/decisions/${decision['id']}';
    final failed = decision['status'] == 'failed';
    final event = switch ('${decision['event']}') {
      'no_show' => 'No-show',
      'client_cancelled' => 'Late cancellation',
      _ => 'Payment',
    };
    void reload() => ref.invalidate(decisionsProvider(businessId));

    return Padding(
      padding: const EdgeInsets.only(bottom: Space.md),
      child: Panel(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(event, style: text.titleMedium)),
            StatusPill(failed ? 'Payment didn’t go through' : 'Waiting for you', state: failed ? MoneyState.problem : MoneyState.waiting),
          ]),
          const SizedBox(height: Space.sm),
          Text('${decision['reason']}', style: text.bodyMedium),
          if (failed && decision['failure_reason'] != null)
            Text('${decision['failure_reason']}', style: text.bodySmall?.copyWith(color: Palette.problem)),
          const SizedBox(height: Space.md),
          Text('Up to ${formatMoney(decision['amount'], currency)} can be kept', style: text.titleSmall?.copyWith(color: Palette.held)),
          const SizedBox(height: Space.lg),
          Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
            if (failed)
              BusyButton(
                label: 'Try again',
                onPressed: () async {
                  if (await runSave(context, () => api.post('$base/retry'), done: 'Tried again with PayPal.')) reload();
                },
              )
            else ...[
              BusyButton(
                label: 'Charge ${formatMoney(decision['amount'], currency)}',
                onPressed: () async {
                  if (await runSave(context, () => api.post('$base/approve', body: const {}), done: 'Charged. A receipt was sent.')) reload();
                },
              ),
              OutlinedButton(
                onPressed: () async {
                  final amount = await _askAmount(context, '${decision['amount']}');
                  if (amount == null || !context.mounted) return;
                  if (await runSave(context, () => api.post('$base/approve', body: {'final_amount': amount}), done: 'Charged the lower amount.')) reload();
                },
                child: const Text('Charge less'),
              ),
              TextButton(
                onPressed: () async {
                  if (await runSave(context, () => api.post('$base/waive', body: const {}), done: 'Waived. Everything was released.')) reload();
                },
                child: const Text('Waive it'),
              ),
            ],
          ]),
        ]),
      ),
    );
  }

  Future<String?> _askAmount(BuildContext context, String max) {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Charge a smaller amount'),
        content: TextField(
          controller: controller,
          autofocus: true,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: InputDecoration(labelText: 'Amount ($currency)', helperText: 'At most ${formatMoney(max, currency)}'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              final value = num.tryParse(controller.text.trim());
              Navigator.of(context).pop(value?.toStringAsFixed(2));
            },
            child: const Text('Charge'),
          ),
        ],
      ),
    );
  }
}
