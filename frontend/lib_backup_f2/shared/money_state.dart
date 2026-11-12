import 'package:flutter/material.dart';

import '../app/tokens.dart';

/// What is happening to someone's money. Each state has one colour and one icon, everywhere in the app.
enum MoneyState {
  held(Palette.held, Palette.heldBg, Icons.lock_outline_rounded),
  waiting(Palette.waiting, Palette.waitingBg, Icons.schedule_rounded),
  charged(Palette.charged, Palette.chargedBg, Icons.receipt_long_outlined),
  released(Palette.released, Palette.releasedBg, Icons.check_circle_outline_rounded),
  problem(Palette.problem, Palette.problemBg, Icons.error_outline_rounded);

  const MoneyState(this.color, this.background, this.icon);
  final Color color;
  final Color background;
  final IconData icon;
}

class StatusPill extends StatelessWidget {
  const StatusPill(this.label, {super.key, required this.state});

  final String label;
  final MoneyState state;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: label,
      child: DecoratedBox(
        decoration: BoxDecoration(color: state.background, borderRadius: BorderRadius.circular(Radii.chip)),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 5, 10, 5),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(state.icon, size: 14, color: state.color),
            const SizedBox(width: 5),
            Text(label, style: Theme.of(context).textTheme.labelSmall?.copyWith(color: state.color)),
          ]),
        ),
      ),
    );
  }
}
