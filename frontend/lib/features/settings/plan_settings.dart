import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/format/money.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'settings_common.dart';

final _planProvider = FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  return asMap(await ref.watch(apiClientProvider).get('/api/owner/businesses/$id/plan'));
});

/// Rebookly's plans, explained plainly: Free (3% of what clients pay for visits) or Pro (monthly, no fee).
class PlanSettingsScreen extends StatelessWidget {
  const PlanSettingsScreen({super.key, this.checkOnOpen = false});

  final bool checkOnOpen;   // true when coming back from PayPal

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'Plan and fees',
        subtitle: 'You only pay Rebookly when clients actually pay you for a visit. Never on cancellations.',
        builder: (context, id, business) => _Plan(businessId: id, checkOnOpen: checkOnOpen),
      );
}

class _Plan extends ConsumerStatefulWidget {
  const _Plan({required this.businessId, required this.checkOnOpen});

  final String businessId;
  final bool checkOnOpen;

  @override
  ConsumerState<_Plan> createState() => _PlanState();
}

class _PlanState extends ConsumerState<_Plan> {
  String get _base => '/api/owner/businesses/${widget.businessId}/plan';

  @override
  void initState() {
    super.initState();
    if (widget.checkOnOpen) {
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (await runSave(context, () => ref.read(apiClientProvider).post('$_base/refresh'), done: 'Checked with PayPal.')) {
          ref.invalidate(_planProvider(widget.businessId));
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final api = ref.read(apiClientProvider);
    void reload() => ref.invalidate(_planProvider(widget.businessId));
    return AsyncView<Map<String, dynamic>>(
      value: ref.watch(_planProvider(widget.businessId)),
      onRetry: reload,
      data: (plan) {
        final pro = plan['pro_active'] == true;
        final currency = '${plan['currency'] ?? 'USD'}';
        final until = plan['pro_until'] == null ? null : DateTime.tryParse('${plan['pro_until']}');
        final percent = num.tryParse('${plan['fee_percent']}')?.toStringAsFixed(0) ?? '3';
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          LayoutBuilder(builder: (context, constraints) {
            final cards = [
              _PlanCard(
              title: 'Free',
              price: 'No monthly price',
              lines: ['$percent% of what a client pays for a visit, split off automatically by PayPal',
                'Nothing on cancellations, no-shows or released deposits', 'Every feature included'],
              current: !pro,
              ),
              _PlanCard(
              title: 'Pro',
              price: '${plan['pro_price'] ?? ''}',
              lines: const ['No per-visit fee at all', 'Paid monthly with PayPal', 'Cancel any time; it runs to the end of the month'],
              current: pro,
              ),
            ];
            return constraints.maxWidth < 620
                ? Column(children: [cards[0], const SizedBox(height: Space.md), cards[1]])
                : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(child: cards[0]),
                    const SizedBox(width: Space.md),
                    Expanded(child: cards[1]),
                  ]);
          }),
          const SizedBox(height: Space.xl),
          Panel(
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Rebookly fees this month', style: text.titleSmall),
                  Text(pro ? 'None while you’re on Pro.' : 'Only from visits clients paid for.', style: text.bodySmall),
                ]),
              ),
              Text(formatMoney(plan['fees_this_month'], currency), style: text.headlineSmall?.copyWith(fontFeatures: Fonts.tabular)),
            ]),
          ),
          const SizedBox(height: Space.xl),
          if (pro) ...[
            if (until != null) Text('Pro is paid up until ${DateFormat('d MMMM yyyy').format(until.toLocal())}.', style: text.bodyMedium),
            const SizedBox(height: Space.md),
            OutlinedButton(
              style: OutlinedButton.styleFrom(foregroundColor: Palette.problem),
              onPressed: () async {
                if (await runSave(context, () => api.post('$_base/cancel'), done: 'Pro cancelled. It runs until the end of the paid month.')) reload();
              },
              child: const Text('Cancel Pro'),
            ),
          ] else if (plan['can_subscribe'] == true) ...[
            BusyButton(
              label: 'Switch to Pro',
              icon: Icons.workspace_premium_outlined,
              onPressed: () async {
                await runSave(context, () async {
                  final json = asMap(await api.post('$_base/subscribe',
                      body: {'return_url': '${Uri.base.origin}/business/settings/plan?check=1'}));
                  await launchUrl(Uri.parse('${json['approve_url']}'), webOnlyWindowName: '_self');
                }, done: 'Opening PayPal…');
              },
            ),
            const SizedBox(height: Space.sm),
            Text('You approve the subscription on PayPal, then come back here.', style: text.bodySmall),
          ] else
            Text('Pro will be available soon.', style: text.bodyMedium?.copyWith(color: Palette.muted)),
        ]);
      },
    );
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({required this.title, required this.price, required this.lines, required this.current});

  final String title;
  final String price;
  final List<String> lines;
  final bool current;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.all(Space.xl),
      decoration: BoxDecoration(
        color: current ? Palette.sage : Palette.surface,
        borderRadius: BorderRadius.circular(Radii.card),
        border: Border.all(color: current ? Palette.forest : Palette.line, width: current ? 1.6 : 1),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(title, style: text.headlineSmall)),
          if (current) const StatusPill('Your plan', state: MoneyState.released),
        ]),
        const SizedBox(height: 4),
        Text(price, style: text.titleMedium),
        const SizedBox(height: Space.md),
        for (final line in lines)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Padding(padding: EdgeInsets.only(top: 2), child: Icon(Icons.check_rounded, size: 18, color: Palette.forest)),
              const SizedBox(width: Space.sm),
              Expanded(child: Text(line, style: text.bodyMedium)),
            ]),
          ),
      ]),
    );
  }
}
