import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../shared/feedback.dart';
import 'settings_common.dart';

/// Tax registration, so tax is shown correctly on prices and receipts. Only needed if you're registered.
class TaxSettingsScreen extends StatelessWidget {
  const TaxSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'Tax',
        subtitle: 'Only if your business is registered for tax (GST, VAT, sales tax). Otherwise leave it off.',
        builder: (context, id, business) => _Tax(businessId: id, business: business),
      );
}

final _taxProvider = FutureProvider.autoDispose.family<Map<String, dynamic>?, String>((ref, id) async {
  try {
    final json = await ref.watch(apiClientProvider).get('/api/owner/businesses/$id/tax-profile');
    return json == null ? null : asMap(json);
  } on ApiException catch (problem) {
    if (problem.isNotFound) return null;
    rethrow;
  }
});

class _Tax extends ConsumerWidget {
  const _Tax({required this.businessId, required this.business});

  final String businessId;
  final Map<String, dynamic> business;

  @override
  Widget build(BuildContext context, WidgetRef ref) => AsyncView<Map<String, dynamic>?>(
        value: ref.watch(_taxProvider(businessId)),
        onRetry: () => ref.invalidate(_taxProvider(businessId)),
        data: (profile) => _TaxForm(businessId: businessId, business: business, profile: profile ?? const {}),
      );
}

class _TaxForm extends ConsumerStatefulWidget {
  const _TaxForm({required this.businessId, required this.business, required this.profile});

  final String businessId;
  final Map<String, dynamic> business;
  final Map<String, dynamic> profile;

  @override
  ConsumerState<_TaxForm> createState() => _TaxFormState();
}

class _TaxFormState extends ConsumerState<_TaxForm> {
  late final p = widget.profile;
  late bool _registered = p['tax_registered'] == true;
  late final _number = TextEditingController(text: '${p['registration_number'] ?? ''}');
  late final _rate = TextEditingController(text: '${p['tax_rate'] ?? ''}');
  late final _legal = TextEditingController(text: '${p['legal_name'] ?? ''}');
  late final _address = TextEditingController(text: '${p['registered_address'] ?? ''}');
  late bool _included = p['prices_include_tax'] != false;
  late bool _feesTaxable = p['fees_taxable'] == true;

  @override
  void dispose() {
    for (final c in [_number, _rate, _legal, _address]) {
      c.dispose();
    }
    super.dispose();
  }

  String get _country => '${widget.business['country_code'] ?? p['country_code'] ?? 'IN'}';
  String get _label => switch (_country) { 'IN' => 'GSTIN', 'GB' || 'IE' => 'VAT number', 'AU' => 'ABN', 'US' => 'EIN', _ => 'Tax number' };

  Future<void> _save() async {
    if (await runSave(context, () => ref.read(apiClientProvider).put('/api/owner/businesses/${widget.businessId}/tax-profile', body: {
          'country_code': _country,
          if (widget.business['region_code'] != null) 'region_code': widget.business['region_code'],
          'tax_registered': _registered,
          if (_registered) ...{
            'registration_number': _number.text.trim(),
            'tax_rate': _rate.text.trim(),
            'prices_include_tax': _included,
            'fees_taxable': _feesTaxable,
            if (_legal.text.trim().isNotEmpty) 'legal_name': _legal.text.trim(),
            if (_address.text.trim().isNotEmpty) 'registered_address': _address.text.trim(),
          },
        }))) {
      ref.invalidate(_taxProvider(widget.businessId));
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: Text('My business is registered for tax', style: text.titleSmall),
        subtitle: Text('Tax is then shown on prices and receipts.', style: text.bodySmall),
        value: _registered,
        onChanged: (value) => setState(() => _registered = value),
      ),
      if (_registered) ...[
        const SizedBox(height: Space.md),
        TextField(controller: _number, textCapitalization: TextCapitalization.characters, decoration: InputDecoration(labelText: _label)),
        const SizedBox(height: Space.md),
        SizedBox(
          width: 200,
          child: TextField(
            controller: _rate,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Tax rate (%)', helperText: 'For example 18'),
          ),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('My prices already include tax'),
          subtitle: const Text('Usual in India, the UK and Australia. In the US and Canada, tax is usually added on top.'),
          value: _included,
          onChanged: (value) => setState(() => _included = value),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Charge tax on cancellation and no-show fees'),
          subtitle: const Text('Ask your accountant if you’re not sure.'),
          value: _feesTaxable,
          onChanged: (value) => setState(() => _feesTaxable = value),
        ),
        TextField(controller: _legal, decoration: const InputDecoration(labelText: 'Legal name (on receipts, optional)')),
        const SizedBox(height: Space.md),
        TextField(controller: _address, maxLines: 2, decoration: const InputDecoration(labelText: 'Registered address (optional)')),
      ],
      const SizedBox(height: Space.xl),
      BusyButton(label: 'Save', onPressed: _save),
      const SizedBox(height: Space.sm),
      Text('The number’s format is checked for your country. Rebookly doesn’t give tax advice.', style: text.bodySmall),
    ]);
  }
}
