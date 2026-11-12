import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/i18n/i18n.dart';
import '../../app/tokens.dart';
import '../../shared/client_shell.dart';
import '../../shared/layout.dart';
import 'landing_parts.dart';

/// For business owners: three steps to start, and the one worry ("what if someone doesn't come?") answered,
/// with a small demo of the decision they make.
class ForBusinessScreen extends StatefulWidget {
  const ForBusinessScreen({super.key});

  @override
  State<ForBusinessScreen> createState() => _ForBusinessScreenState();
}

class _ForBusinessScreenState extends State<ForBusinessScreen> {
  int? _keep;   // the demo decision: 80, 40 or 0

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    Widget row(String label, Widget value) => Padding(
          padding: EdgeInsets.symmetric(vertical: 12),
          child: Row(children: [Expanded(child: Text(label, style: text.bodyLarge)), value]),
        );
    return ClientShell(
      child: SingleChildScrollView(
        child: Column(children: [
          Band(
            child: SideBySide(
              left: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(context.tr('business.title'), style: (wide ? text.displayLarge : text.displayMedium)?.copyWith(fontSize: wide ? 68 : 42)),
                SizedBox(height: Space.lg),
                Text(context.tr('business.lead'),
                    style: text.bodyLarge?.copyWith(color: Palette.muted, fontSize: 18)),
                SizedBox(height: Space.xl),
                Wrap(spacing: Space.md, runSpacing: Space.md, children: [
                  FilledButton(onPressed: () => context.go('/business/start'), child: Text(context.tr('business.cta'))),
                  OutlinedButton(onPressed: () => context.go('/business/signin'), child: Text(context.tr('account.sign_in'))),
                ]),
                SizedBox(height: Space.md),
                Text(context.tr('business.takes_five'), style: text.bodySmall),
              ]),
              right: TiltedTray(
                color: Palette.forestDeep,
                angle: 0.021,
                child: Panel(
                  child: Column(children: [
                    row(context.tr('demo.today'), Text(context.tr('demo.thursday'), style: text.bodySmall)),
                    Divider(),
                    row(context.tr('demo.bookings'), Text('7', style: text.headlineSmall)),
                    Divider(),
                    row(context.tr('demo.kept_by_clients'), Text('₹560', style: text.headlineSmall)),
                    Divider(),
                    row(context.tr('demo.need_decision'), Container(
                      padding: EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(color: Palette.waitingBg, borderRadius: BorderRadius.circular(Radii.chip)),
                      child: Text(context.tr('demo.one_no_show'), style: text.labelSmall?.copyWith(color: Palette.waiting)),
                    )),
                  ]),
                ),
              ),
            ),
          ),
          Band(
            top: 8,
            child: ThreeSteps(steps: [
              StepCard(
                number: 1,
                title: context.tr('business.step1.title'),
                body: context.tr('business.step1.body'),
                show: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Align(alignment: Alignment.centerRight, child: _Bubble(context.tr('business.step1.owner'), mine: true)),
                  SizedBox(height: Space.sm),
                  Align(alignment: Alignment.centerLeft, child: _Bubble(context.tr('business.step1.ai'), mine: false)),
                ]),
              ),
              StepCard(
                number: 2,
                title: context.tr('business.step2.title'),
                body: context.tr('business.step2.body'),
                show: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    padding: EdgeInsets.all(Space.md),
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(Radii.control), border: Border.all(color: Palette.sageDeep)),
                    child: Row(children: [
                      Icon(Icons.link_rounded, size: 18, color: Palette.forest),
                      SizedBox(width: Space.sm),
                      Expanded(child: Text('rebookly.app/b/ravis-barbershop', style: text.titleSmall, overflow: TextOverflow.ellipsis)),
                    ]),
                  ),
                  SizedBox(height: Space.sm),
                  Wrap(spacing: Space.sm, children: [for (final s in ['WhatsApp', 'Instagram', context.tr('business.step2.qr')]) Chip(label: Text(s))]),
                ]),
              ),
              StepCard(
                number: 3,
                title: context.tr('business.step3.title'),
                body: context.tr('business.step3.body'),
                show: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Icon(Icons.notifications_none_rounded, color: Palette.held),
                  SizedBox(width: Space.sm),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(context.tr('demo.new_booking'), style: text.titleSmall),
                      Text(context.tr('business.step3.line'), style: text.bodySmall),
                    ]),
                  ),
                ]),
              ),
            ]),
          ),
          Band(
            top: 0,
            child: Container(
              padding: EdgeInsets.all(wide ? 44 : 24),
              decoration: BoxDecoration(color: Palette.forestDeep, borderRadius: BorderRadius.circular(28)),
              child: SideBySide(
                leftFlex: 9,
                rightFlex: 11,
                gap: 48,
                left: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(context.tr('business.worry.title'), style: text.displaySmall?.copyWith(color: Colors.white)),
                  SizedBox(height: Space.md),
                  Text(context.tr('business.worry.body'),
                      style: text.bodyLarge?.copyWith(color: Palette.sageDeep)),
                ]),
                right: Panel(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(context.tr('business.worry.case'), style: text.titleMedium),
                    Text(context.tr('business.worry.kept'), style: text.bodySmall),
                    SizedBox(height: Space.md),
                    for (final (keep, label, hint) in [(80, context.tr('business.keep80'), context.tr('business.keep80_hint')), (40, context.tr('business.keep40'), context.tr('business.keep40_hint')), (0, context.tr('business.keep0'), context.tr('business.keep0_hint'))])
                      Padding(
                        padding: EdgeInsets.only(bottom: Space.sm),
                        child: Material(
                          color: _keep == keep ? Palette.sage : Palette.surface,
                          borderRadius: BorderRadius.circular(Radii.control),
                          child: InkWell(
                            borderRadius: BorderRadius.circular(Radii.control),
                            onTap: _keep == null ? () => setState(() => _keep = keep) : null,
                            child: Container(
                              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(Radii.control),
                                border: Border.all(color: _keep == keep ? Palette.forest : Palette.line, width: _keep == keep ? 1.6 : 1.2),
                              ),
                              child: Opacity(
                                opacity: _keep == null || _keep == keep ? 1 : 0.45,
                                child: Row(children: [
                                  Expanded(child: Text(label, style: text.titleSmall)),
                                  Text(hint, style: text.bodySmall),
                                ]),
                              ),
                            ),
                          ),
                        ),
                      ),
                    SizedBox(height: Space.sm),
                    Text(
                      _keep == null
                          ? ''
                          : _keep == 0
                              ? context.tr('business.kept_none')
                              : context.tr('business.kept_some', {'keep': _keep, 'back': 80 - _keep!}),
                      style: text.bodyMedium,
                    ),
                  ]),
                ),
              ),
            ),
          ),
          Band(
            top: 8,
            child: Questions(items: [
              (context.tr('business.q1'), context.tr('business.a1')),
              (context.tr('business.q2'), context.tr('business.a2')),
              (context.tr('business.q3'), context.tr('business.a3')),
            ]),
          ),
          Band(
            color: Palette.forestDeep,
            child: Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: Space.xl,
              runSpacing: Space.lg,
              children: [
                Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                  Text(context.tr('business.ready'), style: text.displaySmall?.copyWith(color: Colors.white)),
                  SizedBox(height: Space.sm),
                  Text(context.tr('business.ready_body'), style: text.bodyLarge?.copyWith(color: Palette.sageDeep)),
                ]),
                FilledButton(
                  onPressed: () => context.go('/business/start'),
                  style: FilledButton.styleFrom(backgroundColor: Colors.white, foregroundColor: Palette.forestDeep),
                  child: Text(context.tr('business.cta')),
                ),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble(this.message, {required this.mine});

  final String message;
  final bool mine;

  @override
  Widget build(BuildContext context) => Container(
        constraints: BoxConstraints(maxWidth: 260),
        padding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(color: mine ? Palette.forest : Palette.sage, borderRadius: BorderRadius.circular(14)),
        child: Text(message, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: mine ? Colors.white : Palette.ink)),
      );
}
