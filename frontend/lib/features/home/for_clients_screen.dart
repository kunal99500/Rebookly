import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/i18n/i18n.dart';
import '../../app/tokens.dart';
import '../../shared/client_shell.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'landing_parts.dart';

/// For clients: three easy steps, and the one worry ("what if I can't make it?") answered plainly.
class ForClientsScreen extends StatefulWidget {
  const ForClientsScreen({super.key});

  @override
  State<ForClientsScreen> createState() => _ForClientsScreenState();
}

class _ForClientsScreenState extends State<ForClientsScreen> {
  final _search = TextEditingController();
  String _time = '4:30 PM';

  static const _times = [('11:15 AM', true), ('1:30 PM', false), ('4:30 PM', true), ('5:15 PM', true), ('6:00 PM', false), ('6:45 PM', true)];

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _go() {
    final q = _search.text.trim();
    context.go(q.isEmpty ? '/search' : '/search?q=${Uri.encodeQueryComponent(q)}');
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    return ClientShell(
      child: SingleChildScrollView(
        child: Column(children: [
          Band(
            child: SideBySide(
              left: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(context.tr('clients.title'), style: (wide ? text.displayLarge : text.displayMedium)?.copyWith(fontSize: wide ? 68 : 42)),
                SizedBox(height: Space.lg),
                Text(context.tr('clients.lead'),
                    style: text.bodyLarge?.copyWith(color: Palette.muted, fontSize: 18)),
                SizedBox(height: Space.xl),
                Row(children: [
                  Expanded(
                    child: TextField(
                      controller: _search,
                      onSubmitted: (_) => _go(),
                      decoration: InputDecoration(hintText: context.tr('clients.search_hint'), prefixIcon: Icon(Icons.search_rounded)),
                    ),
                  ),
                  SizedBox(width: Space.sm),
                  FilledButton(onPressed: _go, child: Text(context.tr('common.search'))),
                ]),
              ]),
              right: TiltedTray(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    StatusPill(context.tr('clients.spot_held'), state: MoneyState.held),
                    Spacer(),
                    Text(context.tr('common.example'), style: text.bodySmall),
                  ]),
                  SizedBox(height: Space.md),
                  SimpleTicket(time: _time),
                ]),
              ),
            ),
          ),
          Band(
            top: 8,
            child: ThreeSteps(steps: [
              StepCard(
                number: 1,
                title: context.tr('clients.step1.title'),
                body: context.tr('clients.step1.body'),
                show: Row(children: [
                  Container(
                    width: 52,
                    height: 52,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.control)),
                    child: Text('R', style: text.headlineSmall?.copyWith(color: Palette.forest)),
                  ),
                  SizedBox(width: Space.md),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(context.tr('ticket.example_place'), style: text.titleSmall),
                      Text(context.tr('clients.step1.distance'), style: text.bodySmall),
                      Text(context.tr('clients.step1.rating'), style: text.labelSmall?.copyWith(color: Palette.waiting)),
                    ]),
                  ),
                ]),
              ),
              StepCard(
                number: 2,
                title: context.tr('clients.step2.title'),
                body: context.tr('clients.step2.body'),
                show: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
                    for (final (time, free) in _times)
                      ChoiceChip(
                        label: Text(time.replaceAll(' AM', '').replaceAll(' PM', '')),
                        selected: _time == time,
                        showCheckmark: false,
                        onSelected: free ? (_) => setState(() => _time = time) : null,
                      ),
                  ]),
                  SizedBox(height: Space.sm),
                  Text(context.tr('clients.step2.hint'), style: text.bodySmall),
                ]),
              ),
              StepCard(
                number: 3,
                title: context.tr('clients.step3.title'),
                body: context.tr('clients.step3.body'),
                show: Column(children: [
                  Row(children: [Expanded(child: Text(context.tr('clients.step3.kept_now'), style: text.bodyMedium)), Text('₹80', style: text.headlineSmall?.copyWith(color: Palette.held))]),
                  SizedBox(height: 6),
                  Row(children: [Expanded(child: Text(context.tr('clients.step3.pay_later'), style: text.bodyMedium)), Text('₹370', style: text.headlineSmall)]),
                ]),
              ),
            ]),
          ),
          Band(
            top: 0,
            child: Container(
              padding: EdgeInsets.all(wide ? 44 : 24),
              decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(28)),
              child: SideBySide(
                leftFlex: 9,
                rightFlex: 11,
                gap: 48,
                left: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(context.tr('clients.worry.title'), style: text.displaySmall),
                  SizedBox(height: Space.md),
                  Text(context.tr('clients.worry.body'),
                      style: text.bodyLarge?.copyWith(color: Palette.muted)),
                ]),
                right: Panel(
                  child: Column(children: [
                    RuleLine(free: true, bold: context.tr('clients.worry.early'), rest: context.tr('clients.worry.early_rest')),
                    RuleLine(free: true, bold: context.tr('clients.worry.moved'), rest: context.tr('clients.worry.moved_rest')),
                    RuleLine(free: false, bold: context.tr('clients.worry.late'), rest: context.tr('clients.worry.late_rest')),
                  ]),
                ),
              ),
            ),
          ),
          Band(
            top: 8,
            child: Questions(items: [
              (context.tr('clients.q1'), context.tr('clients.a1')),
              (context.tr('clients.q2'), context.tr('clients.a2')),
              (context.tr('clients.q3'), context.tr('clients.a3')),
            ]),
          ),
        ]),
      ),
    );
  }
}
