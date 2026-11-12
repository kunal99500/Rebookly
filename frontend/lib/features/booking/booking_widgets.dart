import 'package:flutter/material.dart';

import '../../app/tokens.dart';
import '../../shared/hold_ticket.dart';
import '../../shared/layout.dart';
import 'booking_data.dart';

/// A booking step: scrolling content, with the main action pinned to the bottom of the screen.
class StepFrame extends StatelessWidget {
  const StepFrame({super.key, required this.children, this.action, this.summary});

  final List<Widget> children;
  final Widget? action;
  final Widget? summary;   // short text beside the action, e.g. "2 services selected"

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Expanded(child: PageScroll(maxWidth: 820, children: children)),
      if (action != null)
        DecoratedBox(
          decoration: const BoxDecoration(
            color: Palette.surface,
            border: Border(top: BorderSide(color: Palette.line)),
          ),
          child: SafeArea(
            top: false,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 820),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
                  child: Row(children: [
                    Expanded(child: summary ?? const SizedBox.shrink()),
                    const SizedBox(width: Space.md),
                    action!,
                  ]),
                ),
              ),
            ),
          ),
        ),
    ]);
  }
}

/// "Services, Time, Review": where you are in the booking. Finished steps can be tapped to go back.
class StepIndicator extends StatelessWidget {
  const StepIndicator({super.key, required this.current, required this.labels, this.onTap});

  final int current;
  final List<String> labels;
  final void Function(int step)? onTap;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.xl),
      child: Row(children: [
        for (var i = 0; i < labels.length; i++) ...[
          if (i > 0)
            Expanded(
              child: Container(
                height: 2,
                margin: const EdgeInsets.symmetric(horizontal: Space.sm),
                color: i <= current ? Palette.forest : Palette.line,
              ),
            ),
          Semantics(
            button: i < current,
            label: '${labels[i]}${i < current ? ', done' : i == current ? ', current step' : ''}',
            child: InkWell(
              borderRadius: BorderRadius.circular(Radii.chip),
              onTap: i < current && onTap != null ? () => onTap!(i) : null,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 2),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Container(
                    width: 26,
                    height: 26,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: i < current ? Palette.forest : (i == current ? Palette.sage : Palette.surface),
                      border: Border.all(color: i <= current ? Palette.forest : Palette.line),
                      shape: BoxShape.circle,
                    ),
                    child: i < current
                        ? const Icon(Icons.check_rounded, size: 15, color: Colors.white)
                        : Text('${i + 1}', style: text.labelSmall?.copyWith(color: i == current ? Palette.forest : Palette.muted)),
                  ),
                  const SizedBox(width: Space.sm),
                  Text(
                    labels[i],
                    style: text.labelMedium?.copyWith(color: i <= current ? Palette.ink : Palette.muted),
                  ),
                ]),
              ),
            ),
          ),
        ],
      ]),
    );
  }
}

/// The deposit notice before choosing a time: exactly what's held, what's paid later, and the rules.
Future<bool> showDepositNotice(BuildContext context, DepositNotice notice) async {
  final text = Theme.of(context).textTheme;
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (context) => AlertDialog(
      backgroundColor: Palette.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.sheet)),
      titlePadding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
      contentPadding: const EdgeInsets.fromLTRB(24, 12, 24, 8),
      title: Text(notice.title, style: text.headlineSmall),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 440),
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(notice.summary, style: text.bodyMedium?.copyWith(color: Palette.muted)),
            const SizedBox(height: Space.lg),
            for (final line in notice.lines)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(children: [
                  Expanded(child: Text(line.label, style: text.bodyLarge)),
                  Text(line.amount, style: text.titleLarge?.copyWith(fontFeatures: Fonts.tabular)),
                ]),
              ),
            const SizedBox(height: Space.md),
            const Divider(),
            const SizedBox(height: Space.md),
            NoticeRules(policy: notice.policy),
            if (notice.ownerNote != null) ...[
              const SizedBox(height: Space.sm),
              OwnerNote(note: notice.ownerNote!),
            ],
          ]),
        ),
      ),
      actionsPadding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Back')),
        FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Got it, pick a time')),
      ],
    ),
  );
  return result ?? false;
}

/// The backend's policy sentences as tick (costs nothing) and cross (may cost) lines.
class NoticeRules extends StatelessWidget {
  const NoticeRules({super.key, required this.policy});

  final List<String> policy;

  @override
  Widget build(BuildContext context) {
    final rules = policy.map(TicketRule.fromNotice).toList();
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final rule in rules)
        Padding(
          padding: const EdgeInsets.only(bottom: Space.sm),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(
              rule.free ? Icons.check_circle_rounded : Icons.cancel_rounded,
              size: 20,
              color: rule.free ? Palette.released : Palette.problem,
            ),
            const SizedBox(width: Space.sm),
            Expanded(child: Text(rule.text, style: text.bodyMedium)),
          ]),
        ),
    ]);
  }
}

class OwnerNote extends StatelessWidget {
  const OwnerNote({super.key, required this.note});

  final String note;

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(Space.md),
        decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.control)),
        child: Text('“$note”', style: Theme.of(context).textTheme.bodyMedium),
      );
}

/// Asked once, before someone's first booking: the name the business will see.
Future<String?> askForName(BuildContext context) =>
    showDialog<String>(context: context, builder: (context) => const _NameDialog());

class _NameDialog extends StatefulWidget {
  const _NameDialog();

  @override
  State<_NameDialog> createState() => _NameDialogState();
}

class _NameDialogState extends State<_NameDialog> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _save() {
    final name = _controller.text.trim();
    if (name.isNotEmpty) Navigator.of(context).pop(name);
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return AlertDialog(
      backgroundColor: Palette.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.sheet)),
      title: Text('What’s your name?', style: text.headlineSmall),
      content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(
          'The business sees this on your booking. You only need to add it once.',
          style: text.bodyMedium?.copyWith(color: Palette.muted),
        ),
        const SizedBox(height: Space.lg),
        TextField(
          controller: _controller,
          autofocus: true,
          textCapitalization: TextCapitalization.words,
          autofillHints: const [AutofillHints.name],
          maxLength: 80,
          decoration: const InputDecoration(labelText: 'Your name', counterText: ''),
          onSubmitted: (_) => _save(),
        ),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(onPressed: _save, child: const Text('Save and continue')),
      ],
    );
  }
}
