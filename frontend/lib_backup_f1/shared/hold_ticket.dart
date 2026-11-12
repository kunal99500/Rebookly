import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../app/tokens.dart';
import 'money_state.dart';

/// One part of a cancellation policy, drawn as a segment of the ticket's timeline.
class PolicyStep {
  const PolicyStep({required this.label, required this.detail, required this.state, this.flex = 1});

  final String label;   // "Free to cancel"
  final String detail;  // "Until Mon 17 Nov, 4:30 PM"
  final MoneyState state;
  final int flex;
}

/// Rebookly's signature element: a booking as a ticket.
///
/// The top half says what's booked; the tear line separates it from the money: what's held now,
/// what's paid at the visit, and how the cancellation rules play out over time.
/// It sits on a tinted "tray" so the notches in the tear line read as cut-outs.
class HoldTicket extends StatelessWidget {
  const HoldTicket({
    super.key,
    required this.title,
    required this.lines,
    required this.held,
    this.payLater,
    this.steps = const [],
    this.footnote,
    this.trayColor = Palette.sage,
  });

  final String title;
  final List<String> lines;
  final String held;
  final String? payLater;
  final List<PolicyStep> steps;
  final String? footnote;
  final Color trayColor;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Semantics(
      container: true,
      label: 'Booking ticket: $title. $held held, not charged.${payLater == null ? '' : ' $payLater to pay at the visit.'}',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _Half(
          top: true,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: text.headlineSmall),
            const SizedBox(height: Space.sm),
            for (final line in lines)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(line, style: text.bodyMedium?.copyWith(color: Palette.muted)),
              ),
            const SizedBox(height: Space.xl),
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Expanded(child: _Amount(amount: held, caption: 'held now, not charged', color: Palette.held)),
              if (payLater != null)
                _Amount(amount: payLater!, caption: 'paid at the visit', color: Palette.ink, alignEnd: true),
            ]),
          ]),
        ),
        _TearLine(trayColor: trayColor),
        _Half(
          top: false,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (steps.isNotEmpty) _Timeline(steps: steps),
            if (footnote != null) ...[
              if (steps.isNotEmpty) const SizedBox(height: Space.lg),
              Text(footnote!, style: text.bodySmall),
            ],
          ]),
        ),
      ]),
    );
  }
}

class _Half extends StatelessWidget {
  const _Half({required this.top, required this.child});

  final bool top;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    const radius = Radius.circular(Radii.card);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Palette.surface,
        borderRadius: top
            ? const BorderRadius.only(topLeft: radius, topRight: radius)
            : const BorderRadius.only(bottomLeft: radius, bottomRight: radius),
      ),
      child: Padding(
        padding: EdgeInsets.fromLTRB(Space.xl, top ? Space.xl : Space.md, Space.xl, top ? Space.md : Space.xl),
        child: child,
      ),
    );
  }
}

class _Amount extends StatelessWidget {
  const _Amount({required this.amount, required this.caption, required this.color, this.alignEnd = false});

  final String amount;
  final String caption;
  final Color color;
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: alignEnd ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        Text(
          amount,
          style: text.displaySmall?.copyWith(color: color, fontSize: 32, fontFeatures: Fonts.tabular),
        ),
        const SizedBox(height: 2),
        Text(caption, style: text.bodySmall),
      ],
    );
  }
}

/// The perforation: a dashed line with a half-circle notch cut into each side.
class _TearLine extends StatelessWidget {
  const _TearLine({required this.trayColor});

  final Color trayColor;

  @override
  Widget build(BuildContext context) {
    const notch = 26.0;
    return SizedBox(
      height: notch,
      child: Stack(clipBehavior: Clip.none, children: [
        const Positioned.fill(child: ColoredBox(color: Palette.surface)),
        Positioned.fill(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: notch),
            child: CustomPaint(painter: _DashPainter()),
          ),
        ),
        Positioned(left: -notch / 2, top: 0, child: _Notch(color: trayColor, size: notch)),
        Positioned(right: -notch / 2, top: 0, child: _Notch(color: trayColor, size: notch)),
      ]),
    );
  }
}

class _Notch extends StatelessWidget {
  const _Notch({required this.color, required this.size});

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: size,
        height: size,
        child: DecoratedBox(decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
      );
}

class _DashPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Palette.line
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.round;
    const dash = 6.0;
    const gap = 5.0;
    final y = size.height / 2;
    var x = 0.0;
    while (x < size.width) {
      canvas.drawLine(Offset(x, y), Offset(math.min(x + dash, size.width), y), paint);
      x += dash + gap;
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// The cancellation policy as a strip that runs left to right through time.
/// On narrow tickets the same steps stack top to bottom, so nothing wraps awkwardly.
class _Timeline extends StatelessWidget {
  const _Timeline({required this.steps});

  final List<PolicyStep> steps;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return LayoutBuilder(builder: (context, constraints) {
      if (constraints.maxWidth < 380) {
        return Column(children: [
          for (final step in steps)
            Padding(
              padding: const EdgeInsets.only(bottom: Space.sm),
              child: IntrinsicHeight(
                child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Container(
                    width: 5,
                    decoration: BoxDecoration(color: step.state.color, borderRadius: BorderRadius.circular(3)),
                  ),
                  const SizedBox(width: Space.md),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(step.label, style: text.labelMedium?.copyWith(color: step.state.color)),
                      const SizedBox(height: 2),
                      Text(step.detail, style: text.bodySmall),
                    ]),
                  ),
                ]),
              ),
            ),
        ]);
      }
      return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        for (var i = 0; i < steps.length; i++) ...[
          if (i > 0) const SizedBox(width: 6),
          Expanded(
            flex: steps[i].flex,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                height: 6,
                decoration: BoxDecoration(color: steps[i].state.color, borderRadius: BorderRadius.circular(3)),
              ),
              const SizedBox(height: Space.sm),
              Text(steps[i].label, style: text.labelMedium?.copyWith(color: steps[i].state.color)),
              const SizedBox(height: 2),
              Text(steps[i].detail, style: text.bodySmall),
            ]),
          ),
        ],
      ]);
    });
  }
}
