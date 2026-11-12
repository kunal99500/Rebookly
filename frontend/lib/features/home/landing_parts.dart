import 'package:flutter/material.dart';

import '../../core/i18n/i18n.dart';
import '../../app/tokens.dart';
import '../../shared/hold_ticket.dart';
import '../../shared/layout.dart';

/// A full-width band with the page's content width inside.
class Band extends StatelessWidget {
  const Band({super.key, required this.child, this.color, this.top = 64, this.bottom = 64});

  final Widget child;
  final Color? color;
  final double top;
  final double bottom;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    return ColoredBox(
      color: color ?? Colors.transparent,
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: Breakpoints.page),
          child: Padding(
            padding: EdgeInsets.fromLTRB(wide ? 40 : 20, wide ? top : top * 0.6, wide ? 40 : 20, wide ? bottom : bottom * 0.7),
            child: child,
          ),
        ),
      ),
    );
  }
}

/// Two pieces side by side on wide screens, stacked on phones.
class SideBySide extends StatelessWidget {
  const SideBySide({super.key, required this.left, required this.right, this.leftFlex = 11, this.rightFlex = 9, this.gap = 64});

  final Widget left;
  final Widget right;
  final int leftFlex;
  final int rightFlex;
  final double gap;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    if (!wide) return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [left, SizedBox(height: 40), right]);
    return Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
      Expanded(flex: leftFlex, child: left),
      SizedBox(width: gap),
      Expanded(flex: rightFlex, child: right),
    ]);
  }
}

/// The landing pages' example ticket: plain words, a tick and a cross.
class SimpleTicket extends StatelessWidget {
  const SimpleTicket({super.key, this.time = '4:30 PM', this.tray = Palette.sage});

  final String time;   // the example time, e.g. "4:30 PM"
  final Color tray;

  @override
  Widget build(BuildContext context) => HoldTicket(
        title: context.tr('ticket.example_service'),
        lines: [context.tr('ticket.example_place'), context.tr('ticket.example_when', {'time': time})],
        held: '₹80',
        heldCaption: context.tr('ticket.kept_aside'),
        payLater: '₹370',
        payLaterCaption: context.tr('ticket.pay_when_you_come'),
        trayColor: tray,
        rules: [
          TicketRule(context.tr('ticket.cancel_before', {'time': time}), free: true),
          TicketRule(context.tr('ticket.cancel_late'), free: false),
        ],
      );
}

/// A tray with a slight tilt on wide screens: the landing pages' one bold gesture.
class TiltedTray extends StatelessWidget {
  const TiltedTray({super.key, required this.child, this.color = Palette.sage, this.angle = -0.025});

  final Widget child;
  final Color color;
  final double angle;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    final tray = DecoratedBox(
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(Radii.sheet)),
      child: Padding(padding: EdgeInsets.all(18), child: child),
    );
    final animate = !reduceMotion(context);
    final tilted = Transform.rotate(angle: wide ? angle : 0, child: tray);
    if (!animate) return tilted;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 800),
      curve: Curves.easeOutCubic,
      builder: (context, t, child) => Opacity(opacity: t, child: Transform.translate(offset: Offset(0, 24 * (1 - t)), child: child)),
      child: tilted,
    );
  }
}

/// A numbered step card with a small piece of the app below it.
class StepCard extends StatelessWidget {
  const StepCard({super.key, required this.number, required this.title, required this.body, required this.show});

  final int number;
  final String title;
  final String body;
  final Widget show;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      padding: EdgeInsets.all(Space.xl),
      decoration: BoxDecoration(color: Palette.surface, borderRadius: BorderRadius.circular(20), border: Border.all(color: Palette.line)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          width: 32,
          height: 32,
          alignment: Alignment.center,
          decoration: BoxDecoration(color: Palette.sage, shape: BoxShape.circle),
          child: Text('$number', style: text.titleSmall?.copyWith(color: Palette.forest)),
        ),
        SizedBox(height: Space.lg),
        Text(title, style: text.headlineSmall),
        SizedBox(height: Space.sm),
        Text(body, style: text.bodyLarge?.copyWith(color: Palette.muted)),
        SizedBox(height: Space.lg),
        Divider(),
        SizedBox(height: Space.lg),
        show,
      ]),
    );
  }
}

/// Three step cards in a row on wide screens, stacked on phones.
class ThreeSteps extends StatelessWidget {
  const ThreeSteps({super.key, required this.steps});

  final List<Widget> steps;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    if (!wide) {
      return Column(children: [for (final s in steps) Padding(padding: EdgeInsets.only(bottom: Space.lg), child: s)]);
    }
    return IntrinsicHeight(
      child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (var i = 0; i < steps.length; i++) ...[
          if (i > 0) SizedBox(width: 20),
          Expanded(child: steps[i]),
        ],
      ]),
    );
  }
}

/// A tick or a cross line, as on the ticket.
class RuleLine extends StatelessWidget {
  const RuleLine({super.key, required this.free, required this.bold, required this.rest, this.onDark = false});

  final bool free;
  final String bold;
  final String rest;
  final bool onDark;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: EdgeInsets.only(bottom: Space.md),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          width: 26,
          height: 26,
          decoration: BoxDecoration(color: free ? Palette.releasedBg : Palette.problemBg, shape: BoxShape.circle),
          child: Icon(free ? Icons.check_rounded : Icons.close_rounded, size: 16, color: free ? Palette.released : Palette.problem),
        ),
        SizedBox(width: Space.md),
        Expanded(
          child: Text.rich(
            TextSpan(children: [
              TextSpan(text: bold, style: TextStyle(fontWeight: FontWeight.w700)),
              TextSpan(text: rest),
            ]),
            style: text.bodyLarge?.copyWith(color: onDark ? Colors.white : Palette.ink),
          ),
        ),
      ]),
    );
  }
}

/// Short questions and answers that open on tap.
class Questions extends StatelessWidget {
  const Questions({super.key, required this.items});

  final List<(String, String)> items;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(context.tr('landing.questions'), style: text.displaySmall),
      SizedBox(height: Space.lg),
      for (final (question, answer) in items) ...[
        Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            tilePadding: EdgeInsets.zero,
            childrenPadding: EdgeInsets.only(bottom: Space.lg),
            expandedAlignment: Alignment.centerLeft,
            iconColor: Palette.forest,
            collapsedIconColor: Palette.forest,
            title: Text(question, style: text.titleMedium),
            children: [Text(answer, style: text.bodyLarge?.copyWith(color: Palette.muted))],
          ),
        ),
        Divider(),
      ],
    ]);
  }
}
