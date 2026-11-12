import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/money.dart';
import '../../core/format/time.dart';
import '../../shared/feedback.dart';
import 'settings_common.dart';

final _servicesProvider = FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>((ref, id) async {
  return asList(await ref.watch(apiClientProvider).get('/api/owner/businesses/$id/services'));
});

/// Services, extras and classes: what they cost, how long they take, and what's kept aside to book.
class ServicesSettingsScreen extends StatelessWidget {
  const ServicesSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'Services',
        subtitle: 'Main services, extras added to a visit, and group classes.',
        builder: (context, id, business) => _Services(businessId: id, currency: '${business['currency'] ?? 'USD'}'),
      );
}

class _Services extends ConsumerWidget {
  const _Services({required this.businessId, required this.currency});

  final String businessId;
  final String currency;

  Future<void> _edit(BuildContext context, WidgetRef ref, Map<String, dynamic>? service) async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _ServiceEditor(service: service, currency: currency),
    );
    if (result == null || !context.mounted) return;
    final api = ref.read(apiClientProvider);
    final path = '/api/owner/businesses/$businessId/services';
    final saved = await runSave(
      context,
      () => service == null ? api.post(path, body: result) : api.patch('$path/${service['id']}', body: result),
      done: service == null ? 'Service added.' : 'Service saved.',
    );
    if (saved) ref.invalidate(_servicesProvider(businessId));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return AsyncView<List<Map<String, dynamic>>>(
      value: ref.watch(_servicesProvider(businessId)),
      onRetry: () => ref.invalidate(_servicesProvider(businessId)),
      data: (services) {
        Widget group(String title, String kind, String? mode) {
          final items = services.where((s) => s['kind'] == kind && (mode == null || s['booking_mode'] == mode)).toList();
          if (items.isEmpty) return const SizedBox.shrink();
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: text.headlineSmall),
            const SizedBox(height: Space.sm),
            for (final service in items)
              _Row(service: service, currency: currency, onTap: () => _edit(context, ref, service)),
            const SizedBox(height: Space.xl),
          ]);
        }

        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          BusyButton(label: 'Add a service', icon: Icons.add_rounded, onPressed: () => _edit(context, ref, null)),
          const SizedBox(height: Space.xl),
          if (services.isEmpty)
            const EmptyState(icon: Icons.content_cut_rounded, title: 'No services yet', message: 'Add what clients can book.'),
          group('Services', 'main', 'appointment'),
          group('Group classes', 'main', 'class'),
          group('Extras', 'add_on', null),
        ]);
      },
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.service, required this.currency, required this.onTap});

  final Map<String, dynamic> service;
  final String currency;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final active = service['is_active'] != false;
    final deposit = num.tryParse('${service['deposit']}') ?? 0;
    final facts = [
      formatDuration((service['duration_minutes'] as num?)?.toInt() ?? 0),
      if (deposit > 0) '${formatMoney(service['deposit'], currency)} kept aside',
      if (!active) 'hidden from clients',
    ].join(', ');
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
      child: Opacity(
        opacity: active ? 1 : 0.55,
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
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${service['name']}', style: text.titleMedium),
                    Text(facts, style: text.bodySmall),
                  ]),
                ),
                Text(formatMoney(service['price'], currency), style: text.titleMedium?.copyWith(fontFeatures: Fonts.tabular)),
                const SizedBox(width: Space.sm),
                const Icon(Icons.edit_outlined, size: 18, color: Palette.muted),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

class _ServiceEditor extends ConsumerStatefulWidget {
  const _ServiceEditor({required this.service, required this.currency});

  final Map<String, dynamic>? service;
  final String currency;

  @override
  ConsumerState<_ServiceEditor> createState() => _ServiceEditorState();
}

class _ServiceEditorState extends ConsumerState<_ServiceEditor> {
  late final Map<String, dynamic> s = widget.service ?? const {};
  late final _name = TextEditingController(text: '${s['name'] ?? ''}');
  late final _description = TextEditingController(text: '${s['description'] ?? ''}');
  late final _minutes = TextEditingController(text: '${s['duration_minutes'] ?? 30}');
  late final _cleanup = TextEditingController(text: '${s['cleanup_minutes'] ?? 0}');
  late final _price = TextEditingController(text: '${s['price'] ?? ''}');
  late final _deposit = TextEditingController(text: '${s['deposit'] ?? ''}');
  late final _capacity = TextEditingController(text: '${s['capacity'] ?? 10}');
  late String _kind = '${s['kind'] ?? 'main'}';
  late String _mode = '${s['booking_mode'] ?? 'appointment'}';
  late bool _active = s['is_active'] != false;
  String? _error;

  @override
  void dispose() {
    for (final c in [_name, _description, _minutes, _cleanup, _price, _deposit, _capacity]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _suggestDeposit() async {
    final price = num.tryParse(_price.text.trim());
    if (price == null) return;
    try {
      final json = await ref.read(apiClientProvider).post('/api/owner/deposits/preview',
          body: {'currency': widget.currency, 'percent': '10', 'prices': [price.toString()]});
      setState(() => _deposit.text = '${((json as Map)['deposits'] as List).first}');
    } on ApiException catch (problem) {
      if (mounted) showMessage(context, problem.message);
    }
  }

  void _done() {
    final minutes = int.tryParse(_minutes.text.trim());
    final price = num.tryParse(_price.text.trim());
    final deposit = _kind == 'add_on' ? 0 : (num.tryParse(_deposit.text.trim()) ?? 0);
    if (_name.text.trim().length < 2 || minutes == null || minutes < 5 || price == null) {
      setState(() => _error = 'Add a name, at least 5 minutes, and a price.');
      return;
    }
    if (deposit > price) {
      setState(() => _error = 'The amount kept aside can’t be more than the price.');
      return;
    }
    Navigator.of(context).pop({
      'name': _name.text.trim(),
      'description': _description.text.trim().isEmpty ? null : _description.text.trim(),
      'kind': _kind,
      'booking_mode': _kind == 'add_on' ? 'appointment' : _mode,
      'duration_minutes': minutes,
      'cleanup_minutes': int.tryParse(_cleanup.text.trim()) ?? 0,
      'price': price.toStringAsFixed(2),
      'deposit': deposit.toStringAsFixed(2),
      'payment_options': deposit > 0 ? ['deposit_held', 'full_held'] : ['full_held'],
      if (_mode == 'class' && _kind != 'add_on') 'capacity': int.tryParse(_capacity.text.trim()) ?? 10,
      if (widget.service != null) 'is_active': _active,
    });
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final extra = _kind == 'add_on';
    return AlertDialog(
      title: Text(widget.service == null ? 'Add a service' : 'Change service'),
      content: SizedBox(
        width: 460,
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Wrap(spacing: Space.sm, children: [
              for (final (kind, mode, label) in const [('main', 'appointment', 'Service'), ('main', 'class', 'Group class'), ('add_on', 'appointment', 'Extra')])
                ChoiceChip(
                  label: Text(label),
                  selected: _kind == kind && (kind == 'add_on' || _mode == mode),
                  showCheckmark: false,
                  onSelected: (_) => setState(() {
                    _kind = kind;
                    _mode = mode;
                  }),
                ),
            ]),
            const SizedBox(height: Space.md),
            TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
            const SizedBox(height: Space.md),
            TextField(controller: _description, maxLines: 3, decoration: const InputDecoration(labelText: 'Description (optional)')),
            const SizedBox(height: Space.md),
            Row(children: [
              Expanded(child: TextField(controller: _minutes, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Minutes'))),
              const SizedBox(width: Space.md),
              Expanded(
                child: TextField(
                  controller: _cleanup,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Clean-up after', helperText: 'Minutes blocked after'),
                ),
              ),
            ]),
            const SizedBox(height: Space.md),
            TextField(
              controller: _price,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(labelText: 'Price (${widget.currency})'),
            ),
            if (!extra) ...[
              const SizedBox(height: Space.md),
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _deposit,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Kept aside to book'),
                  ),
                ),
                TextButton(onPressed: _suggestDeposit, child: const Text('Use 10%')),
              ]),
            ],
            if (_mode == 'class' && !extra) ...[
              const SizedBox(height: Space.md),
              TextField(controller: _capacity, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Places per session')),
            ],
            if (widget.service != null)
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Clients can book this'),
                value: _active,
                onChanged: (value) => setState(() => _active = value),
              ),
            if (_error != null) Text(_error!, style: text.bodyMedium?.copyWith(color: Palette.problem)),
          ]),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(onPressed: _done, child: const Text('Save')),
      ],
    );
  }
}
