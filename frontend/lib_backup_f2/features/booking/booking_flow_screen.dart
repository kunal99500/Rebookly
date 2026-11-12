import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../app/tokens.dart';
import '../../core/api/api_exception.dart';
import '../../core/auth/auth_service.dart';
import '../../core/format/money.dart';
import '../../core/format/time.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/hold_ticket.dart';
import '../../shared/layout.dart';
import '../business/business_data.dart';
import 'booking_data.dart';
import 'booking_widgets.dart';
import 'flow_state.dart';
import 'waitlist_sheet.dart';

const _stepLabels = ['Services', 'Time', 'Review'];

/// Booking a visit: choose services, pick a time, review and hold the deposit with PayPal.
class BookingFlowScreen extends ConsumerWidget {
  const BookingFlowScreen({super.key, required this.slug, required this.query});

  final String slug;
  final Map<String, String> query;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final page = ref.watch(businessPageProvider(slug));
    return ClientShell(
      showNavigation: false,
      child: AsyncView<BusinessPage>(
        value: page,
        page: true,
        onRetry: () => ref.invalidate(businessPageProvider(slug)),
        data: (business) {
          final state = FlowState.fromQuery(query);
          final known = {for (final s in business.services) s.id: s};

          if (state.isClass) {
            final service = known[state.classId];
            if (service == null || !service.isClass) return _StartAgain(slug: slug);
            return state.slotId == null
                ? ClassSessionsStep(business: business, service: service, state: state)
                : ClassReviewStep(business: business, service: service, state: state);
          }
          final valid = state.serviceIds.every(known.containsKey);
          if (state.serviceIds.isEmpty || !valid || state.editing) {
            return ServicesStep(
              key: ValueKey(state.serviceIds.join(',')),
              business: business,
              initial: valid ? state.serviceIds : const [],
            );
          }
          if (state.time == null) {
            return TimeStep(key: ValueKey('${state.serviceIds.join(',')}|${state.staffFilter}'), business: business, state: state);
          }
          return ReviewStep(key: ValueKey(state.time), business: business, state: state);
        },
      ),
    );
  }
}

String _visitName(BusinessPage business, List<String> ids) {
  final names = {for (final s in business.services) s.id: s.name};
  return ids.map((id) => names[id] ?? '').where((n) => n.isNotEmpty).join(' + ');
}

class _StartAgain extends StatelessWidget {
  const _StartAgain({required this.slug});

  final String slug;

  @override
  Widget build(BuildContext context) => PageScroll(maxWidth: 720, children: [
        EmptyState(
          icon: Icons.refresh_rounded,
          title: 'This booking link is out of date',
          message: 'The business may have changed its services. Start again to see what’s available now.',
          action: FilledButton(onPressed: () => context.go('/b/$slug/book'), child: const Text('Start again')),
        ),
      ]);
}

// =====================================================================
// Step 1: choose services
// =====================================================================

class ServicesStep extends StatefulWidget {
  const ServicesStep({super.key, required this.business, required this.initial});

  final BusinessPage business;
  final List<String> initial;

  @override
  State<ServicesStep> createState() => _ServicesStepState();
}

class _ServicesStepState extends State<ServicesStep> {
  late final Set<String> _selected = {...widget.initial};

  List<ServiceItem> get _mains => widget.business.services.where((s) => !s.isAddOn && !s.isClass).toList();
  List<ServiceItem> get _classes => widget.business.services.where((s) => s.isClass).toList();
  List<ServiceItem> get _extras => widget.business.addOns;
  bool get _hasMain => _mains.any((s) => _selected.contains(s.id));

  void _toggle(ServiceItem service) {
    setState(() {
      if (_selected.remove(service.id)) {
        // Extras need a main service: if none is left, untick the extras too.
        if (!service.isAddOn && !_hasMain) _selected.removeAll(_extras.map((s) => s.id));
      } else {
        _selected.add(service.id);
      }
    });
  }

  void _continue() {
    // The backend expects main services first, then extras.
    final ids = [
      ..._mains.where((s) => _selected.contains(s.id)).map((s) => s.id),
      ..._extras.where((s) => _selected.contains(s.id)).map((s) => s.id),
    ];
    const FlowState().withServices(ids).go(context, widget.business.slug);
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final business = widget.business;
    final count = _selected.length;
    return StepFrame(
      summary: Text(
        count == 0 ? 'Choose at least one service' : '$count selected',
        style: text.titleSmall?.copyWith(color: count == 0 ? Palette.muted : Palette.ink),
      ),
      action: FilledButton(onPressed: _hasMain ? _continue : null, child: const Text('Choose a time')),
      children: [
        const StepIndicator(current: 0, labels: _stepLabels),
        Text('What would you like?', style: text.displaySmall),
        const SizedBox(height: Space.sm),
        Text(business.name, style: text.bodyLarge?.copyWith(color: Palette.muted)),
        const SizedBox(height: Space.xl),
        if (_mains.isEmpty && _classes.isEmpty)
          const EmptyState(
            icon: Icons.content_cut_rounded,
            title: 'Nothing to book yet',
            message: 'This business hasn’t added any services yet. Check back soon.',
          ),
        for (final service in _mains)
          _ServiceTile(
            service: service,
            currency: business.currency,
            selected: _selected.contains(service.id),
            onTap: () => _toggle(service),
          ),
        if (_extras.isNotEmpty) ...[
          const SizedBox(height: Space.xl),
          SectionHeader(
            'Extras',
            subtitle: _hasMain ? 'Added to the same visit.' : 'Choose a service first, then add extras to it.',
          ),
          for (final service in _extras)
            _ServiceTile(
              service: service,
              currency: business.currency,
              selected: _selected.contains(service.id),
              enabled: _hasMain,
              onTap: () => _toggle(service),
            ),
        ],
        if (_classes.isNotEmpty) ...[
          const SizedBox(height: Space.xl),
          const SectionHeader('Group classes', subtitle: 'Booked one session at a time.'),
          for (final service in _classes)
            _ServiceTile(
              service: service,
              currency: business.currency,
              selected: false,
              trailingAction: 'Choose a session',
              onTap: () => FlowState.forClass(service.id).go(context, business.slug),
            ),
        ],
      ],
    );
  }
}

class _ServiceTile extends StatelessWidget {
  const _ServiceTile({
    required this.service,
    required this.currency,
    required this.selected,
    required this.onTap,
    this.enabled = true,
    this.trailingAction,
  });

  final ServiceItem service;
  final String currency;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;
  final String? trailingAction;   // for classes: a link instead of a tick

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final deposit = num.tryParse(service.deposit) ?? 0;
    final facts = [
      formatDuration(service.durationMinutes),
      if (!service.isAddOn && deposit > 0) '${formatMoney(service.deposit, currency)} kept aside to book',
    ].join(', ');

    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
      child: Opacity(
        opacity: enabled ? 1 : 0.5,
        child: Semantics(
          button: true,
          selected: selected,
          enabled: enabled,
          child: Material(
            color: selected ? Palette.sage : Palette.surface,
            borderRadius: BorderRadius.circular(Radii.card),
            child: InkWell(
              borderRadius: BorderRadius.circular(Radii.card),
              onTap: enabled ? onTap : null,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 160),
                padding: const EdgeInsets.all(Space.lg),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(Radii.card),
                  border: Border.all(color: selected ? Palette.forest : Palette.line, width: selected ? 1.6 : 1),
                ),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  if (trailingAction == null) ...[
                    Padding(
                      padding: const EdgeInsets.only(top: 1),
                      child: Icon(
                        selected ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                        color: selected ? Palette.forest : Palette.faint,
                      ),
                    ),
                    const SizedBox(width: Space.md),
                  ],
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(service.name, style: text.titleMedium),
                      const SizedBox(height: 2),
                      Text(facts, style: text.bodySmall),
                      if (service.description != null && service.description!.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Text(service.description!, style: text.bodyMedium?.copyWith(color: Palette.muted)),
                      ],
                    ]),
                  ),
                  const SizedBox(width: Space.md),
                  Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                    Text(
                      service.isAddOn ? '+${formatMoney(service.price, currency)}' : formatMoney(service.price, currency),
                      style: text.titleMedium?.copyWith(fontFeatures: Fonts.tabular),
                    ),
                    if (trailingAction != null) ...[
                      const SizedBox(height: Space.sm),
                      Text(trailingAction!, style: text.labelMedium?.copyWith(color: Palette.forest)),
                    ],
                  ]),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// =====================================================================
// Step 2: pick a time
// =====================================================================

class TimeStep extends ConsumerStatefulWidget {
  const TimeStep({super.key, required this.business, required this.state});

  final BusinessPage business;
  final FlowState state;

  @override
  ConsumerState<TimeStep> createState() => _TimeStepState();
}

class _TimeStepState extends ConsumerState<TimeStep> {
  bool _noticeHandled = false;
  String? _day;

  AvailabilityKey get _key =>
      (slug: widget.business.slug, serviceIds: widget.state.serviceIds.join(','), staffId: widget.state.staffFilter);

  void _maybeShowNotice(Availability availability) {
    if (_noticeHandled || !availability.showNoticeBeforeTimes) return;
    _noticeHandled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      final ok = await showDepositNotice(context, availability.notice);
      if (!ok && mounted) widget.state.editServices().go(context, widget.business.slug);
    });
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final business = widget.business;
    final value = ref.watch(availabilityProvider(_key));
    final availability = value.valueOrNull;

    return StepFrame(
      summary: availability == null
          ? null
          : Text(
              '${_visitName(business, widget.state.serviceIds)}, ${formatDuration(availability.durationMinutes)}',
              style: text.titleSmall,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
      action: availability == null
          ? null
          : OutlinedButton(
              onPressed: () => showDepositNotice(context, availability.notice),
              child: const Text('Deposit and rules'),
            ),
      children: [
        StepIndicator(
          current: 1,
          labels: _stepLabels,
          onTap: (_) => widget.state.editServices().go(context, business.slug),
        ),
        Text('Pick a time', style: text.displaySmall),
        const SizedBox(height: Space.sm),
        Text('Only times that are really free are shown, in ${business.name}’s local time.',
            style: text.bodyLarge?.copyWith(color: Palette.muted)),
        const SizedBox(height: Space.xl),
        AsyncView<Availability>(
          value: value,
          onRetry: () => ref.invalidate(availabilityProvider(_key)),
          data: (availability) {
            _maybeShowNotice(availability);
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              if (availability.staffChoices.length > 1) ...[
                _StaffPicker(choices: availability.staffChoices, state: widget.state, slug: business.slug),
                const SizedBox(height: Space.xl),
              ],
              if (availability.times.isEmpty)
                EmptyState(
                  icon: Icons.event_busy_outlined,
                  title: 'No free times in the next few days',
                  message: widget.state.staffFilter != null
                      ? 'Try “Anyone”, or ask to be told when a time opens.'
                      : 'Ask to be told when a time opens. If someone cancels, you’ll hear first.',
                  action: FilledButton.icon(
                    onPressed: () => showWaitlistSheet(context, ref, business: business, serviceIds: widget.state.serviceIds),
                    icon: const Icon(Icons.notifications_active_outlined, size: 20),
                    label: const Text('Tell me if a time opens'),
                  ),
                )
              else
                _TimeGrid(
                  times: availability.times,
                  timezone: business.timezone,
                  selectedDay: _day,
                  onDay: (day) => setState(() => _day = day),
                  onTime: (slot) => widget.state
                      .withTime(slot.raw, widget.state.staffFilter ?? (slot.staff.isEmpty ? null : slot.staff.first.id))
                      .go(context, business.slug),
                  onWaitlist: () => showWaitlistSheet(context, ref, business: business, serviceIds: widget.state.serviceIds),
                ),
            ]);
          },
        ),
      ],
    );
  }
}

class _StaffPicker extends StatelessWidget {
  const _StaffPicker({required this.choices, required this.state, required this.slug});

  final List<StaffChoice> choices;
  final FlowState state;
  final String slug;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('With', style: text.titleSmall),
      const SizedBox(height: Space.sm),
      Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
        ChoiceChip(
          label: const Text('Anyone free'),
          selected: state.staffFilter == null,
          showCheckmark: false,
          onSelected: (_) => state.withStaffFilter(null).go(context, slug),
        ),
        for (final person in choices)
          ChoiceChip(
            label: Text(person.name),
            selected: state.staffFilter == person.id,
            showCheckmark: false,
            onSelected: (_) => state.withStaffFilter(person.id).go(context, slug),
          ),
      ]),
    ]);
  }
}

class _TimeGrid extends StatelessWidget {
  const _TimeGrid({
    required this.times,
    required this.timezone,
    required this.selectedDay,
    required this.onDay,
    required this.onTime,
    required this.onWaitlist,
  });

  final List<TimeSlot> times;
  final String timezone;
  final String? selectedDay;
  final ValueChanged<String> onDay;
  final ValueChanged<TimeSlot> onTime;
  final VoidCallback onWaitlist;

  static final _dayKey = DateFormat('yyyy-MM-dd');

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final byDay = <String, List<TimeSlot>>{};
    for (final slot in times) {
      byDay.putIfAbsent(_dayKey.format(inZone(slot.startsAt, timezone)), () => []).add(slot);
    }
    final days = byDay.keys.toList()..sort();
    final day = days.contains(selectedDay) ? selectedDay! : days.first;
    final now = inZone(DateTime.now(), timezone);
    final today = _dayKey.format(now);
    final tomorrow = _dayKey.format(now.add(const Duration(days: 1)));

    String dayLabel(String key) {
      if (key == today) return 'Today';
      if (key == tomorrow) return 'Tomorrow';
      return DateFormat('EEE d MMM').format(DateTime.parse(key));
    }

    final parts = <String, List<TimeSlot>>{'Morning': [], 'Afternoon': [], 'Evening': []};
    for (final slot in byDay[day]!) {
      final hour = inZone(slot.startsAt, timezone).hour;
      parts[hour < 12 ? 'Morning' : (hour < 17 ? 'Afternoon' : 'Evening')]!.add(slot);
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(children: [
          for (final key in days)
            Padding(
              padding: const EdgeInsets.only(right: Space.sm),
              child: ChoiceChip(
                label: Text(dayLabel(key)),
                selected: key == day,
                showCheckmark: false,
                onSelected: (_) => onDay(key),
              ),
            ),
        ]),
      ),
      const SizedBox(height: Space.xl),
      for (final part in parts.entries)
        if (part.value.isNotEmpty) ...[
          Text(part.key, style: text.titleSmall?.copyWith(color: Palette.muted)),
          const SizedBox(height: Space.sm),
          Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
            for (final slot in part.value) _TimeChip(label: formatTime(slot.startsAt, timezone), onTap: () => onTime(slot)),
          ]),
          const SizedBox(height: Space.xl),
        ],
      TextButton.icon(
        onPressed: onWaitlist,
        icon: const Icon(Icons.notifications_none_rounded, size: 20),
        label: const Text('None of these work? Tell me if a better time opens'),
      ),
    ]);
  }
}

class _TimeChip extends StatelessWidget {
  const _TimeChip({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 104,
        child: OutlinedButton(
          onPressed: onTap,
          style: OutlinedButton.styleFrom(
            minimumSize: const Size(0, 48),
            padding: EdgeInsets.zero,
            backgroundColor: Palette.surface,
            textStyle: Theme.of(context).textTheme.labelLarge?.copyWith(fontFeatures: Fonts.tabular),
          ),
          child: Text(label),
        ),
      );
}

// =====================================================================
// Step 3: review and hold the deposit
// =====================================================================

class ReviewStep extends ConsumerStatefulWidget {
  const ReviewStep({super.key, required this.business, required this.state});

  final BusinessPage business;
  final FlowState state;

  @override
  ConsumerState<ReviewStep> createState() => _ReviewStepState();
}

class _ReviewStepState extends ConsumerState<ReviewStep> {
  final _attendee = TextEditingController();
  bool _forSomeoneElse = false;
  bool _busy = false;
  ApiException? _problem;

  @override
  void dispose() {
    _attendee.dispose();
    super.dispose();
  }

  AvailabilityKey get _key =>
      (slug: widget.business.slug, serviceIds: widget.state.serviceIds.join(','), staffId: widget.state.staffFilter);

  Future<void> _pay(String option) async {
    final auth = ref.read(authServiceProvider);
    if (!auth.isSignedIn) {
      final here = GoRouterState.of(context).uri.toString();
      context.go(Uri(path: '/signin', queryParameters: {'from': here}).toString());
      return;
    }
    setState(() {
      _busy = true;
      _problem = null;
    });
    try {
      final api = ref.read(bookingApiProvider);
      if (!await api.hasProfile()) {
        if (!mounted) return;
        final name = await askForName(context);
        if (name == null) return;
        await api.saveName(name);
      }
      final started = await api.startAppointment(
        serviceIds: widget.state.serviceIds,
        startsAt: widget.state.time!,
        staffId: widget.state.staffId,
        paymentOption: option,
        attendeeName: _forSomeoneElse ? _attendee.text.trim() : null,
      );
      if (mounted) goToCheckout(context, widget.business.slug, started);
    } on ApiException catch (problem) {
      if (mounted) setState(() => _problem = problem);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final business = widget.business;
    final value = ref.watch(availabilityProvider(_key));
    return AsyncView<Availability>(
      value: value,
      page: true,
      onRetry: () => ref.invalidate(availabilityProvider(_key)),
      data: (availability) {
        TimeSlot? slot;
        for (final candidate in availability.times) {
          if (candidate.raw == widget.state.time) slot = candidate;
        }
        if (slot == null) {
          return StepFrame(children: [
            const StepIndicator(current: 2, labels: _stepLabels),
            EmptyState(
              icon: Icons.event_busy_outlined,
              title: 'That time was just taken',
              message: 'Someone else booked it a moment ago. Pick another time; your services are still chosen.',
              action: FilledButton(
                onPressed: () => widget.state.backToTimes().go(context, business.slug),
                child: const Text('Pick another time'),
              ),
            ),
          ]);
        }
        return _review(context, availability, slot);
      },
    );
  }

  Widget _review(BuildContext context, Availability availability, TimeSlot slot) {
    final text = Theme.of(context).textTheme;
    final business = widget.business;
    final state = widget.state;
    final option = state.pay ?? (availability.offersDeposit ? 'deposit_held' : 'full_held');
    final deposit = option == 'deposit_held';
    final notice = availability.notice;
    final held = deposit && notice.lines.isNotEmpty ? notice.lines.first.amount : formatMoney(availability.totalPrice, availability.currency);
    final payLater = deposit && notice.lines.length > 1 ? notice.lines[1].amount : null;
    final staff = [...slot.staff, ...availability.staffChoices];
    final staffName = staff.where((p) => p.id == state.staffId).map((p) => p.name).firstOrNull;

    return StepFrame(
      summary: Text(
        _busy ? 'Getting PayPal ready…' : 'Nothing is taken now. You finish on PayPal.',
        style: text.bodySmall,
      ),
      action: FilledButton(
        onPressed: _busy ? null : () => _pay(option),
        child: _busy
            ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
            : Text('Hold $held with PayPal'),
      ),
      children: [
        StepIndicator(
          current: 2,
          labels: _stepLabels,
          onTap: (step) => step == 0
              ? state.editServices().go(context, business.slug)
              : state.backToTimes().go(context, business.slug),
        ),
        Text('Check and hold your spot', style: text.displaySmall),
        const SizedBox(height: Space.xl),
        DecoratedBox(
          decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.sheet)),
          child: Padding(
            padding: const EdgeInsets.all(Space.lg),
            child: HoldTicket(
              title: _visitName(business, state.serviceIds),
              lines: [
                business.name,
                '${formatDayTime(slot.startsAt, business.timezone)}${staffName == null ? '' : ' with $staffName'}',
              ],
              held: held,
              heldCaption: 'kept aside, not taken',
              payLater: payLater,
              payLaterCaption: 'you pay when you come',
              rules: (deposit ? notice.policy : business.policyLines).map(TicketRule.fromNotice).toList(),
              footnote: notice.ownerNote == null ? null : '“${notice.ownerNote}”, ${business.name}',
            ),
          ),
        ),
        const SizedBox(height: Space.xl),
        _TotalRow(label: 'Total for the visit', amount: formatMoney(availability.totalPrice, availability.currency)),
        if (availability.taxLabel != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              'Includes ${availability.taxLabel} of ${formatMoney(availability.taxAmount, availability.currency)}',
              style: text.bodySmall,
            ),
          ),
        if (availability.offersDeposit && availability.offersFull) ...[
          const SizedBox(height: Space.xl),
          Text('How would you like to hold it?', style: text.titleMedium),
          const SizedBox(height: Space.sm),
          _PayOption(
            title: 'Keep a deposit aside',
            subtitle: notice.lines.length > 1
                ? '${notice.lines.first.amount} now, the rest when you come'
                : 'A smaller amount now, the rest when you come',
            selected: deposit,
            onTap: () => state.withPay('deposit_held').go(context, business.slug),
          ),
          _PayOption(
            title: 'Keep the full amount aside',
            subtitle: '${formatMoney(availability.totalPrice, availability.currency)} now, nothing to pay when you come',
            selected: !deposit,
            onTap: () => state.withPay('full_held').go(context, business.slug),
          ),
        ],
        const SizedBox(height: Space.lg),
        CheckboxListTile(
          value: _forSomeoneElse,
          onChanged: (value) => setState(() => _forSomeoneElse = value ?? false),
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          title: Text('I’m booking for someone else', style: text.bodyLarge),
        ),
        if (_forSomeoneElse)
          TextField(
            controller: _attendee,
            maxLength: 80,
            textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(labelText: 'Their name', counterText: ''),
          ),
        if (_problem != null) ...[
          const SizedBox(height: Space.lg),
          ErrorPanel(error: _problem!),
          if (_problem!.isConflict)
            Padding(
              padding: const EdgeInsets.only(top: Space.md),
              child: OutlinedButton(
                onPressed: () => state.backToTimes().go(context, business.slug),
                child: const Text('Pick another time'),
              ),
            ),
        ],
      ],
    );
  }
}

class _TotalRow extends StatelessWidget {
  const _TotalRow({required this.label, required this.amount});

  final String label;
  final String amount;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Row(children: [
      Expanded(child: Text(label, style: text.titleMedium)),
      Text(amount, style: text.headlineSmall?.copyWith(fontFeatures: Fonts.tabular)),
    ]);
  }
}

class _PayOption extends StatelessWidget {
  const _PayOption({required this.title, required this.subtitle, required this.selected, required this.onTap});

  final String title;
  final String subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
      child: Semantics(
        button: true,
        selected: selected,
        child: Material(
          color: selected ? Palette.sage : Palette.surface,
          borderRadius: BorderRadius.circular(Radii.control),
          child: InkWell(
            borderRadius: BorderRadius.circular(Radii.control),
            onTap: onTap,
            child: Container(
              padding: const EdgeInsets.all(Space.lg),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(Radii.control),
                border: Border.all(color: selected ? Palette.forest : Palette.line, width: selected ? 1.6 : 1),
              ),
              child: Row(children: [
                Icon(
                  selected ? Icons.radio_button_checked_rounded : Icons.radio_button_unchecked_rounded,
                  color: selected ? Palette.forest : Palette.faint,
                ),
                const SizedBox(width: Space.md),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(title, style: text.titleSmall),
                    Text(subtitle, style: text.bodySmall),
                  ]),
                ),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

/// After the booking is started: off to the page that opens PayPal and waits for the hold.
void goToCheckout(BuildContext context, String slug, BookingStarted started) {
  context.go(Uri(path: '/my/bookings/${started.bookingId}/checkout', queryParameters: {
    'pay': started.checkoutUrl,
    'until': started.paymentExpiresAt.toUtc().toIso8601String(),
    'from': slug,
  }).toString());
}

// =====================================================================
// Group classes: choose a session, then review
// =====================================================================

class ClassSessionsStep extends ConsumerWidget {
  const ClassSessionsStep({super.key, required this.business, required this.service, required this.state});

  final BusinessPage business;
  final ServiceItem service;
  final FlowState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final key = (slug: business.slug, serviceId: service.id);
    return StepFrame(children: [
      StepIndicator(current: 1, labels: const ['Class', 'Session', 'Review'], onTap: (_) => context.go('/b/${business.slug}/book')),
      Text(service.name, style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text('${formatDuration(service.durationMinutes)} group class at ${business.name}.',
          style: text.bodyLarge?.copyWith(color: Palette.muted)),
      const SizedBox(height: Space.xl),
      AsyncView<List<ClassSession>>(
        value: ref.watch(classSessionsProvider(key)),
        onRetry: () => ref.invalidate(classSessionsProvider(key)),
        data: (sessions) {
          if (sessions.isEmpty) {
            return const EmptyState(
              icon: Icons.groups_2_outlined,
              title: 'No sessions with free seats right now',
              message: 'New sessions open a few days ahead. Check back soon.',
            );
          }
          return Column(children: [
            for (final session in sessions)
              Padding(
                padding: const EdgeInsets.only(bottom: Space.sm),
                child: Material(
                  color: Palette.surface,
                  borderRadius: BorderRadius.circular(Radii.card),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(Radii.card),
                    onTap: () => state.withSlot(session.id).go(context, business.slug),
                    child: Container(
                      padding: const EdgeInsets.all(Space.lg),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(Radii.card),
                        border: Border.all(color: Palette.line),
                      ),
                      child: Row(children: [
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(formatDay(session.startsAt, business.timezone), style: text.titleMedium),
                            Text(
                              '${formatTime(session.startsAt, business.timezone)} to ${formatTime(session.endsAt, business.timezone)}',
                              style: text.bodySmall,
                            ),
                          ]),
                        ),
                        Text(
                          session.seatsLeft == 1 ? '1 seat left' : '${session.seatsLeft} seats left',
                          style: text.labelMedium?.copyWith(color: session.seatsLeft <= 2 ? Palette.waiting : Palette.forest),
                        ),
                        const SizedBox(width: Space.sm),
                        const Icon(Icons.chevron_right_rounded, color: Palette.muted),
                      ]),
                    ),
                  ),
                ),
              ),
          ]);
        },
      ),
    ]);
  }
}

class ClassReviewStep extends ConsumerStatefulWidget {
  const ClassReviewStep({super.key, required this.business, required this.service, required this.state});

  final BusinessPage business;
  final ServiceItem service;
  final FlowState state;

  @override
  ConsumerState<ClassReviewStep> createState() => _ClassReviewStepState();
}

class _ClassReviewStepState extends ConsumerState<ClassReviewStep> {
  bool _busy = false;
  ApiException? _problem;

  Future<void> _pay(String option) async {
    if (!ref.read(authServiceProvider).isSignedIn) {
      final here = GoRouterState.of(context).uri.toString();
      context.go(Uri(path: '/signin', queryParameters: {'from': here}).toString());
      return;
    }
    setState(() {
      _busy = true;
      _problem = null;
    });
    try {
      final api = ref.read(bookingApiProvider);
      if (!await api.hasProfile()) {
        if (!mounted) return;
        final name = await askForName(context);
        if (name == null) return;
        await api.saveName(name);
      }
      final started = await api.startClass(slotId: widget.state.slotId!, paymentOption: option);
      if (mounted) goToCheckout(context, widget.business.slug, started);
    } on ApiException catch (problem) {
      if (mounted) setState(() => _problem = problem);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final business = widget.business;
    final service = widget.service;
    final key = (slug: business.slug, serviceId: service.id);

    return AsyncView<List<ClassSession>>(
      value: ref.watch(classSessionsProvider(key)),
      page: true,
      onRetry: () => ref.invalidate(classSessionsProvider(key)),
      data: (sessions) {
        final session = sessions.where((s) => s.id == widget.state.slotId).firstOrNull;
        if (session == null) {
          return StepFrame(children: [
            EmptyState(
              icon: Icons.event_busy_outlined,
              title: 'That session just filled up',
              message: 'Choose another session.',
              action: FilledButton(
                onPressed: () => widget.state.backToSessions().go(context, business.slug),
                child: const Text('See other sessions'),
              ),
            ),
          ]);
        }
        final offersDeposit = service.paymentOptions.contains('deposit_held');
        final option = widget.state.pay ?? (offersDeposit ? 'deposit_held' : 'full_held');
        final held = option == 'deposit_held'
            ? formatMoney(service.deposit, business.currency)
            : formatMoney(service.price, business.currency);

        return StepFrame(
          summary: Text('Nothing is taken now. You finish on PayPal.', style: text.bodySmall),
          action: FilledButton(
            onPressed: _busy ? null : () => _pay(option),
            child: _busy
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
                : Text('Hold $held with PayPal'),
          ),
          children: [
            StepIndicator(
              current: 2,
              labels: const ['Class', 'Session', 'Review'],
              onTap: (step) => step == 0
                  ? context.go('/b/${business.slug}/book')
                  : widget.state.backToSessions().go(context, business.slug),
            ),
            Text('Check and hold your seat', style: text.displaySmall),
            const SizedBox(height: Space.xl),
            DecoratedBox(
              decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.sheet)),
              child: Padding(
                padding: const EdgeInsets.all(Space.lg),
                child: HoldTicket(
                  title: service.name,
                  lines: [
                    business.name,
                    '${formatDayTime(session.startsAt, business.timezone)}, group class',
                    'Class price ${formatMoney(service.price, business.currency)}',
                  ],
                  held: held,
                  heldCaption: 'kept aside, not taken',
                  rules: business.policyLines.map(TicketRule.fromNotice).toList(),
                  footnote: 'Any tax is added on the PayPal page, where you see the exact total before you approve.',
                ),
              ),
            ),
            if (offersDeposit && service.paymentOptions.contains('full_held')) ...[
              const SizedBox(height: Space.xl),
              _PayOption(
                title: 'Keep a deposit aside',
                subtitle: '${formatMoney(service.deposit, business.currency)} now, the rest when you come',
                selected: option == 'deposit_held',
                onTap: () => widget.state.withPay('deposit_held').go(context, business.slug),
              ),
              _PayOption(
                title: 'Keep the full price aside',
                subtitle: '${formatMoney(service.price, business.currency)} now, nothing to pay when you come',
                selected: option == 'full_held',
                onTap: () => widget.state.withPay('full_held').go(context, business.slug),
              ),
            ],
            if (_problem != null) ...[
              const SizedBox(height: Space.lg),
              ErrorPanel(error: _problem!),
            ],
          ],
        );
      },
    );
  }
}
