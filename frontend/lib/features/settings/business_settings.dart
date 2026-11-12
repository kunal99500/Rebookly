import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../shared/categories.dart';
import '../../shared/layout.dart';
import '../owner/owner_data.dart';
import 'settings_common.dart';

/// Business details, who gets alerts, when clients see the deposit, and whether the business is listed.
class BusinessSettingsScreen extends StatelessWidget {
  const BusinessSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'Business details',
        subtitle: 'What clients see on your page, and how Rebookly reaches you.',
        builder: (context, id, business) => _Form(businessId: id, business: business),
      );
}

class _Form extends ConsumerStatefulWidget {
  const _Form({required this.businessId, required this.business});

  final String businessId;
  final Map<String, dynamic> business;

  @override
  ConsumerState<_Form> createState() => _FormState();
}

class _FormState extends ConsumerState<_Form> {
  late final Map<String, dynamic> b = widget.business;
  late final _name = TextEditingController(text: '${b['name'] ?? ''}');
  late final _description = TextEditingController(text: '${b['description'] ?? ''}');
  late final _phone = TextEditingController(text: '${b['phone'] ?? ''}');
  late final _email = TextEditingController(text: '${b['notification_email'] ?? ''}');
  late final _note = TextEditingController(text: '${b['deposit_notice_note'] ?? ''}');
  late String _category = '${b['category'] ?? 'other'}';
  late String _timing = '${b['deposit_notice_timing'] ?? 'booking_start'}';
  late bool _listed = b['listed_publicly'] != false;

  @override
  void dispose() {
    for (final c in [_name, _description, _phone, _email, _note]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _orNull(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

  Future<void> _save() async {
    final saved = await runSave(context, () => ref.read(apiClientProvider).patch('/api/owner/businesses/${widget.businessId}', body: {
          'name': _name.text.trim(),
          'category': _category,
          'description': _orNull(_description),
          'phone': _orNull(_phone),
          'notification_email': _orNull(_email),
          'deposit_notice_timing': _timing,
          'deposit_notice_note': _orNull(_note),
          'listed_publicly': _listed,
        }));
    if (saved) {
      ref.invalidate(businessDetailProvider(widget.businessId));
      ref.invalidate(ownedBusinessesProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader('About your business'),
      TextField(controller: _name, maxLength: 120, decoration: const InputDecoration(labelText: 'Business name', counterText: '')),
      const SizedBox(height: Space.md),
      DropdownMenu<String>(
        initialSelection: _category,
        label: const Text('Type of business'),
        dropdownMenuEntries: [for (final e in categorySingular.entries) DropdownMenuEntry(value: e.key, label: e.value)],
        onSelected: (value) => setState(() => _category = value ?? _category),
      ),
      const SizedBox(height: Space.md),
      TextField(
        controller: _description,
        minLines: 2,
        maxLines: 5,
        maxLength: 1000,
        decoration: const InputDecoration(labelText: 'A short description for clients'),
      ),
      TextField(controller: _phone, keyboardType: TextInputType.phone, decoration: const InputDecoration(labelText: 'Business phone (optional)')),
      const SizedBox(height: 40),
      const SectionHeader('Alerts', subtitle: 'New bookings, fees waiting for you, payment problems and reviews.'),
      TextField(
        controller: _email,
        keyboardType: TextInputType.emailAddress,
        decoration: const InputDecoration(labelText: 'Send alerts to this email'),
      ),
      const SizedBox(height: 40),
      const SectionHeader('When clients see the deposit', subtitle: 'They always see it before paying. You choose how early.'),
      for (final (value, title, detail) in const [
        ('business_page', 'On my page', 'A banner on your booking page'),
        ('booking_start', 'When they start booking', 'A short box before they choose a time (recommended)'),
        ('checkout', 'Just before paying', 'Only on the final check before PayPal'),
      ])
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(
            _timing == value ? Icons.radio_button_checked_rounded : Icons.radio_button_unchecked_rounded,
            color: _timing == value ? Palette.forest : Palette.faint,
          ),
          onTap: () => setState(() => _timing = value),
          title: Text(title, style: text.titleSmall),
          subtitle: Text(detail, style: text.bodySmall),
        ),
      TextField(
        controller: _note,
        maxLength: 160,
        decoration: const InputDecoration(labelText: 'A short note with the deposit (optional)', hintText: 'Please arrive 5 minutes early'),
      ),
      const SizedBox(height: Space.xl),
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: Text('Show my business in search', style: text.titleSmall),
        subtitle: Text('Turn off to take bookings only through your own link.', style: text.bodySmall),
        value: _listed,
        onChanged: (value) => setState(() => _listed = value),
      ),
      const SizedBox(height: Space.xl),
      BusyButton(label: 'Save', onPressed: _save),
      const SizedBox(height: Space.sm),
      Text('Your booking address (/b/${b['slug']}) stays the same, so links you’ve shared keep working.', style: text.bodySmall),
    ]);
  }
}
