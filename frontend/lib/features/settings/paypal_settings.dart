import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'settings_common.dart';

final _paypalProvider = FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  return asMap(await ref.watch(apiClientProvider).get('/api/owner/businesses/$id/paypal'));
});

/// Connect the owner's own PayPal account, so deposits and payments go straight to them.
class PayPalSettingsScreen extends StatelessWidget {
  const PayPalSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'PayPal',
        subtitle: 'Deposits and payments go straight to your own PayPal account. Rebookly never holds your money.',
        builder: (context, id, business) => _PayPal(businessId: id),
      );
}

class _PayPal extends ConsumerWidget {
  const _PayPal({required this.businessId});

  final String businessId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final api = ref.read(apiClientProvider);
    final base = '/api/owner/businesses/$businessId/paypal';
    void reload() => ref.invalidate(_paypalProvider(businessId));
    return AsyncView<Map<String, dynamic>>(
      value: ref.watch(_paypalProvider(businessId)),
      onRetry: reload,
      data: (status) {
        final state = '${status['status'] ?? 'not_connected'}';
        final connected = state == 'connected';
        final problems = [for (final p in (status['problems'] as List? ?? const [])) '$p'];
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Panel(
            child: Row(children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(color: Palette.heldBg, borderRadius: BorderRadius.circular(Radii.control)),
                child: const Icon(Icons.account_balance_wallet_outlined, color: Palette.held),
              ),
              const SizedBox(width: Space.lg),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('PayPal', style: text.titleMedium),
                  Text(status['merchant_id_masked'] != null ? 'Account ${status['merchant_id_masked']}' : 'Not connected yet', style: text.bodySmall),
                ]),
              ),
              StatusPill(
                connected ? 'Connected' : (state == 'needs_attention' ? 'Needs attention' : (state == 'pending' ? 'Waiting for PayPal' : 'Not connected')),
                state: connected ? MoneyState.released : (state == 'not_connected' ? MoneyState.charged : MoneyState.waiting),
              ),
            ]),
          ),
          if (problems.isNotEmpty) ...[
            const SizedBox(height: Space.lg),
            Panel(
              color: Palette.waitingBg,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('To finish, in your PayPal account:', style: text.titleSmall),
                for (final problem in problems) Padding(padding: const EdgeInsets.only(top: 4), child: Text('• $problem')),
              ]),
            ),
          ],
          const SizedBox(height: Space.xl),
          Wrap(spacing: Space.md, runSpacing: Space.md, children: [
            if (!connected)
              BusyButton(
                label: state == 'not_connected' ? 'Connect PayPal' : 'Continue on PayPal',
                icon: Icons.open_in_new_rounded,
                onPressed: () async {
                  await runSave(context, () async {
                    final json = asMap(await api.post('$base/connect', body: {'return_url': '${Uri.base.origin}/business/settings/paypal'}));
                    final url = '${json['action_url'] ?? json['url'] ?? json['link'] ?? ''}';
                    if (url.isNotEmpty) await launchUrl(Uri.parse(url), webOnlyWindowName: '_self');
                  }, done: 'Opening PayPal…');
                },
              ),
            OutlinedButton.icon(
              icon: const Icon(Icons.refresh_rounded, size: 20),
              label: const Text('Check again'),
              onPressed: () async {
                if (await runSave(context, () => api.post('$base/refresh'), done: 'Checked with PayPal.')) reload();
              },
            ),
            if (connected)
              TextButton(
                style: TextButton.styleFrom(foregroundColor: Palette.problem),
                onPressed: () async {
                  final sure = await showDialog<bool>(
                    context: context,
                    builder: (context) => AlertDialog(
                      title: const Text('Disconnect PayPal?'),
                      content: const Text('Clients won’t be able to book until you connect an account again. '
                          'This isn’t possible while deposits are still held.'),
                      actions: [
                        TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Keep it')),
                        FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Disconnect')),
                      ],
                    ),
                  );
                  if (sure == true && context.mounted && await runSave(context, () => api.delete(base), done: 'Disconnected.')) reload();
                },
                child: const Text('Disconnect'),
              ),
          ]),
          const SizedBox(height: Space.md),
          Text('When you come back from PayPal, press “Check again” if the status hasn’t changed yet.', style: text.bodySmall),
        ]);
      },
    );
  }
}
