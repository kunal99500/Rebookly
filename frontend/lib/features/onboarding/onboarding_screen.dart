import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/money.dart';
import '../../core/format/time.dart';
import '../../shared/categories.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/mic_button.dart';
import '../../shared/owner_shell.dart';
import '../owner/owner_data.dart';
import 'onboarding_data.dart';

enum _Stage { describe, questions, drafting, review }

/// Set up a business from a description: a few quick questions, then a draft to check and edit before saving.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  _Stage _stage = _Stage.describe;
  final _description = TextEditingController();
  final _currency = TextEditingController(text: 'INR');
  final _timezone = TextEditingController(text: 'Asia/Kolkata');
  String _country = 'IN';

  final List<Map<String, String>> _answers = [];
  InterviewTurn? _turn;
  final Map<String, Set<String>> _chosen = {};
  final Map<String, TextEditingController> _typed = {};

  Map<String, dynamic>? _draft;
  String _depositChoice = '10';   // 10, 20, 30, 50 (percent of the price) or "fixed"
  final _fixedDeposit = TextEditingController();
  List<String> _warnings = const [];
  Map<String, dynamic> _preview = const {};

  bool _busy = false;
  Object? _error;

  @override
  void dispose() {
    for (final c in [_description, _currency, _timezone, _fixedDeposit, ..._typed.values]) {
      c.dispose();
    }
    super.dispose();
  }

  // ---------- steps ----------

  Future<void> _ask({required int round}) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final turn = await ref.read(onboardingApiProvider).interview(
            description: _description.text.trim(),
            answers: _answers,
            country: _country,
            currency: _currency.text.trim().toUpperCase(),
            timezone: _timezone.text.trim(),
            round: round,
          );
      if (turn.ready) {
        await _makeDraft();
        return;
      }
      setState(() {
        _turn = turn;
        _chosen.clear();
        _stage = _Stage.questions;
      });
    } catch (error) {
      setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _collectAnswers() {
    for (final question in _turn?.questions ?? const <InterviewQuestion>[]) {
      final chosen = _chosen[question.id] ?? const <String>{};
      final typed = _typed[question.id]?.text.trim() ?? '';
      final answer = [...chosen, if (typed.isNotEmpty) typed].join(', ');
      if (answer.isNotEmpty) _answers.add({'question': question.text, 'answer': answer});
    }
  }

  Future<void> _makeDraft() async {
    setState(() {
      _stage = _Stage.drafting;
      _error = null;
    });
    try {
      final result = await ref.read(onboardingApiProvider).draft(
            description: _description.text.trim(),
            answers: _answers,
            country: _country,
            currency: _currency.text.trim().toUpperCase(),
            timezone: _timezone.text.trim(),
          );
      setState(() {
        // A deep copy we can edit freely; it goes back to the backend in the same shape.
        _draft = jsonDecode(jsonEncode(result.draft)) as Map<String, dynamic>;
        _warnings = result.warnings;
        _preview = result.preview;
        _stage = _Stage.review;
      });
      await _applyDepositRule();
    } catch (error) {
      setState(() {
        _error = error;
        _stage = _turn == null ? _Stage.describe : _Stage.questions;
      });
    }
  }

  /// Works out every main service's deposit from the owner's rule, on the server (whole units, a small minimum,
  /// never above the price). Extras have no deposit of their own.
  Future<void> _applyDepositRule() async {
    final draft = _draft;
    if (draft == null) return;
    final services = (draft['services'] as List).cast<Map<String, dynamic>>();
    final mains = services.where((s) => s['kind'] != 'add_on').toList();
    final fixed = _depositChoice == 'fixed' ? num.tryParse(_fixedDeposit.text.trim()) : null;
    if (mains.isEmpty || (_depositChoice == 'fixed' && fixed == null)) return;
    final business = draft['business'] as Map<String, dynamic>;
    try {
      final json = await ref.read(apiClientProvider).post('/api/owner/deposits/preview', body: {
        'currency': (business['currency'] ?? _currency.text).toString(),
        if (fixed != null) 'fixed': fixed.toString() else 'percent': _depositChoice,
        'prices': [for (final service in mains) '${service['price']}'],
      });
      final deposits = ((json as Map)['deposits'] as List).map((d) => d.toString()).toList();
      if (!mounted) return;
      setState(() {
        for (var i = 0; i < mains.length && i < deposits.length; i++) {
          mains[i]['deposit'] = deposits[i];
          mains[i]['payment_options'] = (num.tryParse(deposits[i]) ?? 0) > 0 ? ['deposit_held', 'full_held'] : ['full_held'];
        }
        draft['deposit_percent'] = fixed == null ? _depositChoice : null;
        draft['deposit_fixed'] = fixed?.toString();
      });
    } on ApiException catch (problem) {
      if (mounted) showMessage(context, problem.message);
    }
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final applied = await ref.read(onboardingApiProvider).apply(_draft!);
      ref.invalidate(ownedBusinessesProvider);
      if (mounted) context.go('/business/setup?business=${applied.businessId}&policy=${applied.policyVersion}');
    } catch (error) {
      setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // ---------- views ----------

  @override
  Widget build(BuildContext context) {
    final body = switch (_stage) {
      _Stage.describe => _describe(context),
      _Stage.questions => _questions(context),
      _Stage.drafting => _drafting(context),
      _Stage.review => _review(context),
    };
    return OwnerShell(title: 'Set up with AI', child: body);
  }

  Widget _errorBox() => _error == null
      ? const SizedBox.shrink()
      : Padding(padding: const EdgeInsets.only(top: Space.lg), child: ErrorPanel(error: _error!));

  Widget _describe(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final countries = ref.watch(countriesProvider).valueOrNull ?? const <Country>[];
    return PageScroll(maxWidth: 760, children: [
      Text('Tell us about your business', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text(
        'A sentence or two is enough, like “I have a barbershop in Bandra. Haircuts ₹300.” '
        'We’ll ask a few quick questions, then draft your services, hours and cancellation rules for you to check.',
        style: text.bodyLarge?.copyWith(color: Palette.muted),
      ),
      const SizedBox(height: Space.xl),
      TextField(
        controller: _description,
        autofocus: true,
        minLines: 4,
        maxLines: 8,
        maxLength: 3000,
        textCapitalization: TextCapitalization.sentences,
        decoration: InputDecoration(
          hintText: 'What you offer, prices if you know them, your hours, how you handle late cancellations…',
          helperText: 'Tap the microphone to speak instead, in any language.',
          suffixIcon: MicButton(onText: (words) => appendSpoken(_description, words)),
        ),
      ),
      const SizedBox(height: Space.lg),
      LayoutBuilder(builder: (context, constraints) {
        final narrow = constraints.maxWidth < 560;
        final fields = [
          DropdownMenu<String>(
            initialSelection: _country,
            label: const Text('Country'),
            enableFilter: true,
            requestFocusOnTap: true,
            width: narrow ? constraints.maxWidth : 260,
            menuHeight: 320,
            dropdownMenuEntries: [
              for (final country in countries) DropdownMenuEntry(value: country.code, label: country.name),
              if (countries.isEmpty) const DropdownMenuEntry(value: 'IN', label: 'India'),
            ],
            onSelected: (code) {
              if (code == null) return;
              setState(() {
                _country = code;
                if (defaultCurrency[code] != null) _currency.text = defaultCurrency[code]!;
                if (defaultTimezone[code] != null) _timezone.text = defaultTimezone[code]!;
              });
            },
          ),
          SizedBox(
            width: narrow ? constraints.maxWidth : 120,
            child: TextField(
              controller: _currency,
              textCapitalization: TextCapitalization.characters,
              inputFormatters: [LengthLimitingTextInputFormatter(3)],
              decoration: const InputDecoration(labelText: 'Currency'),
            ),
          ),
          SizedBox(
            width: narrow ? constraints.maxWidth : 220,
            child: TextField(controller: _timezone, decoration: const InputDecoration(labelText: 'Time zone')),
          ),
        ];
        return Wrap(spacing: Space.md, runSpacing: Space.md, children: fields);
      }),
      _errorBox(),
      const SizedBox(height: Space.xl),
      FilledButton.icon(
        onPressed: _busy
            ? null
            : () {
                if (_description.text.trim().length < 3) {
                  setState(() => _error = const ApiException('Write a few words about your business first.'));
                  return;
                }
                _answers.clear();
                _turn = null;
                _ask(round: 0);
              },
        icon: _busy
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
            : const Icon(Icons.auto_awesome_outlined, size: 20),
        label: const Text('Continue'),
      ),
      const SizedBox(height: Space.md),
      Text('Nothing is saved until you check the draft and press Save.', style: text.bodySmall),
    ]);
  }

  Widget _questions(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final turn = _turn!;
    return PageScroll(maxWidth: 760, children: [
      Text('A few quick questions', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text(turn.summary, style: text.bodyLarge?.copyWith(color: Palette.muted)),
      const SizedBox(height: Space.xs),
      Text('Round ${turn.round + 1} of ${turn.maxRounds}. Skip anything you’re not sure about.', style: text.bodySmall),
      const SizedBox(height: Space.xl),
      for (final question in turn.questions) ...[
        _QuestionField(
          question: question,
          chosen: _chosen.putIfAbsent(question.id, () => <String>{}),
          typed: _typed.putIfAbsent(question.id, () => TextEditingController()),
          onChanged: () => setState(() {}),
        ),
        const SizedBox(height: Space.xl),
      ],
      _errorBox(),
      Wrap(spacing: Space.md, runSpacing: Space.md, children: [
        FilledButton(
          onPressed: _busy
              ? null
              : () {
                  _collectAnswers();
                  for (final c in _typed.values) {
                    c.clear();
                  }
                  _ask(round: turn.round + 1);
                },
          child: _busy
              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
              : const Text('Continue'),
        ),
        TextButton(
          onPressed: _busy
              ? null
              : () {
                  _collectAnswers();
                  _makeDraft();
                },
          child: const Text('Skip and make my draft now'),
        ),
      ]),
    ]);
  }

  Widget _drafting(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return PageScroll(maxWidth: 760, children: [
      const SizedBox(height: 40),
      const SizedBox(width: 36, height: 36, child: CircularProgressIndicator(strokeWidth: 3)),
      const SizedBox(height: Space.xl),
      Text('Drafting your setup', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text('Services, prices, hours and cancellation rules. This usually takes 10 to 30 seconds.',
          style: text.bodyLarge?.copyWith(color: Palette.muted)),
    ]);
  }

  Widget _review(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final draft = _draft!;
    final business = draft['business'] as Map<String, dynamic>;
    final currency = (business['currency'] ?? _currency.text).toString();
    final services = (draft['services'] as List).cast<Map<String, dynamic>>();
    final needs = [for (final n in (draft['needs_confirmation'] as List? ?? const [])) n.toString()];

    return PageScroll(maxWidth: 820, children: [
      Text('Check your draft', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text('Change anything that isn’t right. Nothing is saved until you press Save.',
          style: text.bodyLarge?.copyWith(color: Palette.muted)),
      if (needs.isNotEmpty || _warnings.isNotEmpty) ...[
        const SizedBox(height: Space.xl),
        Panel(
          color: Palette.waitingBg,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Please check', style: text.titleMedium?.copyWith(color: Palette.waiting)),
            const SizedBox(height: Space.sm),
            for (final line in [...needs, ..._warnings])
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text('• $line', style: text.bodyMedium),
              ),
          ]),
        ),
      ],
      const SizedBox(height: 40),
      const SectionHeader('Your business'),
      TextFormField(
        initialValue: business['name']?.toString() ?? '',
        decoration: const InputDecoration(labelText: 'Business name'),
        onChanged: (value) => business['name'] = value.trim(),
      ),
      const SizedBox(height: Space.md),
      DropdownMenu<String>(
        initialSelection: business['category']?.toString() ?? 'other',
        label: const Text('Type of business'),
        dropdownMenuEntries: [
          for (final entry in categorySingular.entries) DropdownMenuEntry(value: entry.key, label: entry.value),
        ],
        onSelected: (value) => setState(() => business['category'] = value),
      ),
      const SizedBox(height: Space.md),
      TextFormField(
        initialValue: business['description']?.toString() ?? '',
        minLines: 2,
        maxLines: 4,
        maxLength: 1000,
        decoration: const InputDecoration(labelText: 'A short description for clients'),
        onChanged: (value) => business['description'] = value.trim().isEmpty ? null : value.trim(),
      ),
      const SizedBox(height: 40),
      _DepositChooser(
        choice: _depositChoice,
        fixed: _fixedDeposit,
        currency: currency,
        onChoice: (choice) {
          setState(() => _depositChoice = choice);
          _applyDepositRule();
        },
        onFixedDone: _applyDepositRule,
      ),
      const SizedBox(height: 40),
      SectionHeader(
        'Services',
        subtitle: 'Tap one to change it.',
        action: TextButton.icon(
          onPressed: () async {
            final added = await _editService(context, null, currency);
            if (added != null) {
              setState(() => services.add(added));
              await _applyDepositRule();
            }
          },
          icon: const Icon(Icons.add_rounded, size: 20),
          label: const Text('Add'),
        ),
      ),
      for (var i = 0; i < services.length; i++)
        _ServiceRow(
          service: services[i],
          currency: currency,
          onTap: () async {
            final edited = await _editService(context, services[i], currency);
            if (edited != null) setState(() => services[i] = edited);
          },
          onRemove: services.length > 1 ? () => setState(() => services.removeAt(i)) : null,
        ),
      const SizedBox(height: 40),
      const SectionHeader('Opening hours', subtitle: 'You can change hours and add staff in Team and hours after saving.'),
      _HoursSummary(hours: draft['hours'] as Map<String, dynamic>?),
      const SizedBox(height: 40),
      _PolicyEditor(policy: draft['policy'] as Map<String, dynamic>, preview: _preview, currency: currency, onChanged: () => setState(() {})),
      _errorBox(),
      const SizedBox(height: Space.xl),
      Wrap(spacing: Space.md, runSpacing: Space.md, children: [
        FilledButton(
          onPressed: _busy ? null : _save,
          child: _busy
              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
              : const Text('Save my business'),
        ),
        TextButton(onPressed: _busy ? null : () => setState(() => _stage = _Stage.describe), child: const Text('Start over')),
      ]),
      const SizedBox(height: Space.md),
      Text('Your cancellation policy is saved as a draft; you confirm it on the next screen before it applies to anyone.',
          style: text.bodySmall),
    ]);
  }

  Future<Map<String, dynamic>?> _editService(BuildContext context, Map<String, dynamic>? service, String currency) =>
      showDialog<Map<String, dynamic>>(
        context: context,
        builder: (context) => _ServiceDialog(service: service, currency: currency),
      );
}

// ---------- pieces ----------

class _QuestionField extends StatelessWidget {
  const _QuestionField({required this.question, required this.chosen, required this.typed, required this.onChanged});

  final InterviewQuestion question;
  final Set<String> chosen;
  final TextEditingController typed;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final options = question.kind == 'yes_no' ? const ['Yes', 'No'] : question.options;
    final multi = question.kind == 'multi_choice';
    final hasChoices = options.isNotEmpty;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(question.text, style: text.titleMedium),
      const SizedBox(height: Space.sm),
      if (hasChoices)
        Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
          for (final option in options)
            FilterChip(
              label: Text(option),
              selected: chosen.contains(option),
              showCheckmark: multi,
              onSelected: (selected) {
                if (!multi) chosen.clear();
                selected ? chosen.add(option) : chosen.remove(option);
                onChanged();
              },
            ),
        ]),
      if (!hasChoices || question.allowOther) ...[
        if (hasChoices) const SizedBox(height: Space.sm),
        TextField(
          controller: typed,
          keyboardType: question.kind == 'number' ? TextInputType.number : TextInputType.text,
          decoration: InputDecoration(
            hintText: hasChoices ? 'Something else?' : 'Your answer',
            suffixIcon: MicButton(onText: (words) => appendSpoken(typed, words)),
          ),
        ),
      ],
    ]);
  }
}

class _ServiceRow extends StatelessWidget {
  const _ServiceRow({required this.service, required this.currency, required this.onTap, this.onRemove});

  final Map<String, dynamic> service;
  final String currency;
  final VoidCallback onTap;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final kind = service['kind'] == 'add_on' ? 'Extra' : (service['booking_mode'] == 'class' ? 'Group class' : 'Service');
    final facts = [
      kind,
      formatDuration((service['duration_minutes'] as num?)?.toInt() ?? 0),
      if ((num.tryParse('${service['deposit']}') ?? 0) > 0) '${formatMoney(service['deposit'], currency)} kept aside',
    ].join(', ');
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
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
              if (onRemove != null)
                IconButton(tooltip: 'Remove', onPressed: onRemove, icon: const Icon(Icons.close_rounded, color: Palette.muted)),
            ]),
          ),
        ),
      ),
    );
  }
}

class _ServiceDialog extends StatefulWidget {
  const _ServiceDialog({required this.service, required this.currency});

  final Map<String, dynamic>? service;
  final String currency;

  @override
  State<_ServiceDialog> createState() => _ServiceDialogState();
}

class _ServiceDialogState extends State<_ServiceDialog> {
  late final Map<String, dynamic> _s = Map<String, dynamic>.from(widget.service ??
      {
        'name': '',
        'kind': 'main',
        'booking_mode': 'appointment',
        'duration_minutes': 30,
        'cleanup_minutes': 0,
        'price': '0',
        'deposit': '0',
        'payment_options': ['full_held'],
      });
  late final _name = TextEditingController(text: '${_s['name']}');
  late final _minutes = TextEditingController(text: '${_s['duration_minutes']}');
  late final _price = TextEditingController(text: '${_s['price']}');
  late final _deposit = TextEditingController(text: '${_s['deposit']}');
  String? _error;

  @override
  void dispose() {
    for (final c in [_name, _minutes, _price, _deposit]) {
      c.dispose();
    }
    super.dispose();
  }

  void _save() {
    final minutes = int.tryParse(_minutes.text.trim());
    final price = num.tryParse(_price.text.trim());
    final deposit = num.tryParse(_deposit.text.trim()) ?? 0;
    if (_name.text.trim().length < 2 || minutes == null || minutes < 5 || price == null) {
      setState(() => _error = 'Add a name, a length of at least 5 minutes, and a price.');
      return;
    }
    if (deposit > price) {
      setState(() => _error = 'The deposit can’t be more than the price.');
      return;
    }
    final isExtra = _s['kind'] == 'add_on';
    _s
      ..['name'] = _name.text.trim()
      ..['duration_minutes'] = minutes
      ..['price'] = price.toStringAsFixed(2)
      ..['deposit'] = isExtra ? '0.00' : deposit.toStringAsFixed(2)
      ..['payment_options'] = isExtra || deposit == 0 ? ['full_held'] : ['deposit_held', 'full_held'];
    Navigator.of(context).pop(_s);
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final isExtra = _s['kind'] == 'add_on';
    return AlertDialog(
      title: Text(widget.service == null ? 'Add a service' : 'Change service'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
            const SizedBox(height: Space.md),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _minutes,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Minutes'),
                ),
              ),
              const SizedBox(width: Space.md),
              Expanded(
                child: TextField(
                  controller: _price,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: InputDecoration(labelText: 'Price (${widget.currency})'),
                ),
              ),
            ]),
            if (!isExtra) ...[
              const SizedBox(height: Space.md),
              TextField(
                controller: _deposit,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Deposit kept aside to book', helperText: 'About a quarter of the price works well'),
              ),
            ],
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('It’s an extra'),
              subtitle: const Text('Only booked together with a main service'),
              value: isExtra,
              onChanged: (value) => setState(() {
                _s['kind'] = value ? 'add_on' : 'main';
                if (value) _s['booking_mode'] = 'appointment';
              }),
            ),
            if (!isExtra)
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('It’s a group class'),
                subtitle: const Text('Several people at fixed times'),
                value: _s['booking_mode'] == 'class',
                onChanged: (value) => setState(() => _s['booking_mode'] = value ? 'class' : 'appointment'),
              ),
            if (_error != null) Text(_error!, style: text.bodyMedium?.copyWith(color: Palette.problem)),
          ]),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(onPressed: _save, child: const Text('Done')),
      ],
    );
  }
}

class _HoursSummary extends StatelessWidget {
  const _HoursSummary({required this.hours});

  final Map<String, dynamic>? hours;

  static const _days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final list = (hours?['hours'] as List? ?? const []).cast<Map>();
    if (list.isEmpty) {
      return Text('No hours yet. You’ll add them after saving.', style: text.bodyMedium?.copyWith(color: Palette.muted));
    }
    String clock(String value) => value.length >= 5 ? value.substring(0, 5) : value;
    return Panel(
      child: Column(children: [
        for (var day = 0; day < 7; day++)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(children: [
              SizedBox(width: 120, child: Text(_days[day], style: text.bodyMedium)),
              Expanded(
                child: Text(
                  list.where((h) => h['weekday'] == day).map((h) => '${clock('${h['start']}')} to ${clock('${h['end']}')}').join(', ').ifEmpty('Closed'),
                  style: text.bodyMedium?.copyWith(color: Palette.muted),
                ),
              ),
            ]),
          ),
      ]),
    );
  }
}

extension on String {
  String ifEmpty(String fallback) => isEmpty ? fallback : this;
}

class _PolicyEditor extends StatelessWidget {
  const _PolicyEditor({required this.policy, required this.preview, required this.currency, required this.onChanged});

  final Map<String, dynamic> policy;
  final Map<String, dynamic> preview;
  final String currency;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final rules = policy['rules'] as Map<String, dynamic>;
    final rows = (preview['rows'] as List? ?? const []).cast<Map>();

    Widget numberField(String label, String helper, String key, {Map<String, dynamic>? target}) {
      final map = target ?? rules;
      return SizedBox(
        width: 220,
        child: TextFormField(
          initialValue: '${map[key]}',
          keyboardType: TextInputType.number,
          decoration: InputDecoration(labelText: label, helperText: helper, helperMaxLines: 2),
          onChanged: (value) {
            final parsed = num.tryParse(value.trim());
            if (parsed != null) {
              map[key] = key == 'value' ? parsed.toString() : parsed.toInt();
              onChanged();
            }
          },
        ),
      );
    }

    final late = rules['late_cancel_fee'] as Map<String, dynamic>;
    final noShow = rules['no_show_fee'] as Map<String, dynamic>;
    String feeHelper(Map<String, dynamic> fee) => fee['kind'] == 'fixed' ? 'Amount in $currency' : '% of what’s kept aside';

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader('Cancellation rules', subtitle: 'What happens when a client cancels late or doesn’t come.'),
      TextFormField(
        initialValue: '${policy['raw_text']}',
        minLines: 2,
        maxLines: 4,
        maxLength: 2000,
        decoration: const InputDecoration(labelText: 'In plain words (shown to clients)'),
        onChanged: (value) => policy['raw_text'] = value.trim(),
      ),
      const SizedBox(height: Space.md),
      Wrap(spacing: Space.md, runSpacing: Space.md, children: [
        numberField('Free to cancel until', 'Hours before the visit', 'free_cancel_hours'),
        numberField('Late cancellation fee', feeHelper(late), 'value', target: late),
        numberField('No-show fee', feeHelper(noShow), 'value', target: noShow),
        numberField('Grace time', 'Minutes late before it’s a no-show', 'grace_minutes'),
      ]),
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text('No fee if someone else books the time'),
        value: rules['waive_if_refilled'] == true,
        onChanged: (value) {
          rules['waive_if_refilled'] = value;
          onChanged();
        },
      ),
      if (rows.isNotEmpty) ...[
        const SizedBox(height: Space.md),
        Text('Example: how your rules work out for a ${formatMoney(preview['example_hold'], currency)} deposit (each service uses its own):',
            style: text.bodySmall),
        const SizedBox(height: Space.sm),
        Panel(
          padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.sm),
          child: Column(children: [
            for (final row in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(children: [
                  Expanded(child: Text('${row['situation']}', style: text.bodyMedium)),
                  Text(withCurrency('${row['outcome']}', currency), style: text.titleSmall),
                ]),
              ),
          ]),
        ),
        const SizedBox(height: Space.xs),
        Text('If you change the numbers, you’ll see the updated table before confirming.', style: text.bodySmall),
      ],
    ]);
  }
}


/// "How much should clients keep aside to book?" One rule for every service; 10% is suggested.
class _DepositChooser extends StatelessWidget {
  const _DepositChooser({
    required this.choice,
    required this.fixed,
    required this.currency,
    required this.onChoice,
    required this.onFixedDone,
  });

  final String choice;
  final TextEditingController fixed;
  final String currency;
  final ValueChanged<String> onChoice;
  final VoidCallback onFixedDone;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    const options = [('10', '10% (suggested)'), ('20', '20%'), ('30', '30%'), ('50', '50%'), ('fixed', 'A fixed amount')];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader(
        'How much should clients keep aside to book?',
        subtitle: 'Held on their card, not taken. It counts toward their bill when they come.',
      ),
      Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
        for (final (value, label) in options)
          ChoiceChip(
            label: Text(label),
            selected: choice == value,
            showCheckmark: false,
            onSelected: (_) => onChoice(value),
          ),
      ]),
      if (choice == 'fixed') ...[
        const SizedBox(height: Space.md),
        SizedBox(
          width: 220,
          child: TextField(
            controller: fixed,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: 'Amount ($currency)'),
            onSubmitted: (_) => onFixedDone(),
            onEditingComplete: onFixedDone,
          ),
        ),
      ],
      const SizedBox(height: Space.sm),
      Text(
        choice == 'fixed'
            ? 'The same amount for every service (never more than its price).'
            : 'Worked out for each service below: rounded to whole $currency, with a small minimum, never more than the price. '
                'You can still change any single service.',
        style: text.bodySmall,
      ),
    ]);
  }
}
