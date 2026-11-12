import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/format/money.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'settings_common.dart';

final _policiesProvider = FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>((ref, id) async {
  return asList(await ref.watch(apiClientProvider).get('/api/owner/businesses/$id/policies'));
});

/// The cancellation policy: change it as a draft, see exactly what happens in each case, then confirm.
/// Bookings keep the version they were made under; a new version only applies to new bookings.
class PolicySettingsScreen extends StatelessWidget {
  const PolicySettingsScreen({super.key});

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'Cancellation policy',
        subtitle: 'What happens when a client cancels late or doesn’t come. Existing bookings keep the rules they agreed to.',
        builder: (context, id, business) => _Policy(businessId: id, currency: '${business['currency'] ?? 'USD'}'),
      );
}

class _Policy extends ConsumerStatefulWidget {
  const _Policy({required this.businessId, required this.currency});

  final String businessId;
  final String currency;

  @override
  ConsumerState<_Policy> createState() => _PolicyState();
}

class _PolicyState extends ConsumerState<_Policy> {
  Map<String, dynamic>? _rules;
  final _rawText = TextEditingController();
  int? _draftVersion;
  Map<String, dynamic>? _preview;

  String get _base => '/api/owner/businesses/${widget.businessId}/policies';

  @override
  void dispose() {
    _rawText.dispose();
    super.dispose();
  }

  Future<void> _makeDraft() async {
    final api = ref.read(apiClientProvider);
    await runSave(context, () async {
      final draft = asMap(await api.post(_base, body: {'raw_text': _rawText.text.trim(), 'rules': _rules}));
      final version = (draft['version'] as num).toInt();
      final preview = asMap(await api.get('$_base/$version/preview'));
      setState(() {
        _draftVersion = version;
        _preview = preview;
      });
    }, done: 'Draft saved. Check the table, then confirm.');
  }

  Future<void> _confirm() async {
    if (await runSave(context, () => ref.read(apiClientProvider).post('$_base/$_draftVersion/confirm'), done: 'New policy confirmed.')) {
      ref.invalidate(_policiesProvider(widget.businessId));
      ref.invalidate(businessDetailProvider(widget.businessId));
      setState(() {
        _draftVersion = null;
        _preview = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return AsyncView<List<Map<String, dynamic>>>(
      value: ref.watch(_policiesProvider(widget.businessId)),
      onRetry: () => ref.invalidate(_policiesProvider(widget.businessId)),
      data: (policies) {
        final current = policies.where((p) => p['is_current'] == true).firstOrNull ??
            (policies.isEmpty ? null : (policies..sort((a, b) => (b['version'] as num).compareTo(a['version'] as num))).first);
        if (_rules == null) {
          _rules = Map<String, dynamic>.from(current?['rules'] as Map? ??
              {
                'free_cancel_hours': 24,
                'late_cancel_fee': {'kind': 'percent_of_hold', 'value': '50'},
                'no_show_fee': {'kind': 'percent_of_hold', 'value': '100'},
                'waive_if_refilled': true,
                'grace_minutes': 10,
              });
          _rules!['late_cancel_fee'] = Map<String, dynamic>.from(_rules!['late_cancel_fee'] as Map);
          _rules!['no_show_fee'] = Map<String, dynamic>.from(_rules!['no_show_fee'] as Map);
          _rawText.text = '${current?['raw_text'] ?? ''}';
        }
        final rules = _rules!;
        final late = rules['late_cancel_fee'] as Map<String, dynamic>;
        final noShow = rules['no_show_fee'] as Map<String, dynamic>;

        Widget number(String label, String helper, Map<String, dynamic> target, String key, {bool decimal = false}) => SizedBox(
              width: 230,
              child: TextFormField(
                initialValue: '${target[key]}',
                keyboardType: TextInputType.number,
                decoration: InputDecoration(labelText: label, helperText: helper, helperMaxLines: 2),
                onChanged: (value) {
                  final parsed = num.tryParse(value.trim());
                  if (parsed != null) target[key] = decimal ? parsed.toString() : parsed.toInt();
                },
              ),
            );

        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (current != null)
            Padding(
              padding: const EdgeInsets.only(bottom: Space.xl),
              child: Row(children: [
                StatusPill(current['confirmed_at'] != null ? 'In use: version ${current['version']}' : 'Not confirmed yet',
                    state: current['confirmed_at'] != null ? MoneyState.released : MoneyState.waiting),
                const SizedBox(width: Space.md),
                if (current['confirmed_at'] != null)
                  Text('since ${DateFormat('d MMM yyyy').format(DateTime.parse('${current['confirmed_at']}').toLocal())}',
                      style: text.bodySmall),
              ]),
            ),
          TextField(
            controller: _rawText,
            minLines: 2,
            maxLines: 5,
            maxLength: 2000,
            decoration: const InputDecoration(labelText: 'In plain words (shown to clients)'),
          ),
          const SizedBox(height: Space.md),
          Wrap(spacing: Space.md, runSpacing: Space.md, children: [
            number('Free to cancel until', 'Hours before the visit', rules, 'free_cancel_hours'),
            number('Late cancellation keeps', late['kind'] == 'fixed' ? 'Amount in ${widget.currency}' : '% of what’s kept aside', late, 'value', decimal: true),
            number('No-show keeps', noShow['kind'] == 'fixed' ? 'Amount in ${widget.currency}' : '% of what’s kept aside', noShow, 'value', decimal: true),
            number('Grace time', 'Minutes late before it counts as a no-show', rules, 'grace_minutes'),
          ]),
          StatefulBuilder(
            builder: (context, setLocal) => SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('No fee if someone else books the time'),
              value: rules['waive_if_refilled'] == true,
              onChanged: (value) => setLocal(() => rules['waive_if_refilled'] = value),
            ),
          ),
          const SizedBox(height: Space.lg),
          BusyButton(label: 'Preview the changes', icon: Icons.table_rows_outlined, onPressed: _makeDraft),
          if (_preview != null) ...[
            const SizedBox(height: Space.xl),
            Panel(
              color: Palette.waitingBg,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Version $_draftVersion: what happens, for a ${formatMoney(_preview!['example_hold'], widget.currency)} deposit',
                    style: text.titleMedium),
                const SizedBox(height: Space.md),
                for (final row in (_preview!['rows'] as List? ?? const []).cast<Map>())
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Row(children: [
                      Expanded(child: Text('${row['situation']}', style: text.bodyMedium)),
                      Text(withCurrency('${row['outcome']}', widget.currency), style: text.titleSmall),
                    ]),
                  ),
                for (final warning in (_preview!['warnings'] as List? ?? const []))
                  Text('• $warning', style: text.bodySmall?.copyWith(color: Palette.waiting)),
                const SizedBox(height: Space.lg),
                BusyButton(label: 'Confirm this policy', onPressed: _confirm),
                const SizedBox(height: Space.sm),
                Text('Only new bookings use it. Existing bookings keep the rules their clients agreed to.', style: text.bodySmall),
              ]),
            ),
          ],
        ]);
      },
    );
  }
}
