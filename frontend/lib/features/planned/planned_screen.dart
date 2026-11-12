import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../shared/client_shell.dart';
import '../../shared/layout.dart';
import '../../shared/owner_shell.dart';

/// A page whose address and navigation already exist, but whose content arrives in a later build step.
/// It says plainly what the page will do, so the app can be clicked through end to end today.
class PlannedScreen extends StatelessWidget {
  const PlannedScreen({
    super.key,
    required this.title,
    required this.purpose,
    required this.milestone,
    this.owner = false,
  });

  final String title;
  final String purpose;
  final String milestone;   // e.g. "F3: client account"
  final bool owner;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final body = PageScroll(maxWidth: 760, children: [
      Text(title, style: text.displaySmall),
      const SizedBox(height: Space.lg),
      Text(purpose, style: text.bodyLarge?.copyWith(color: Palette.muted)),
      const SizedBox(height: Space.xl),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.chip)),
        child: Text('Being built in $milestone', style: text.labelMedium?.copyWith(color: Palette.forest)),
      ),
      const SizedBox(height: Space.xxl),
      OutlinedButton(
        onPressed: () => context.go(owner ? '/business' : '/'),
        child: Text(owner ? 'Back to today' : 'Back to the home page'),
      ),
    ]);
    return owner ? OwnerShell(title: title, child: body) : ClientShell(child: body);
  }
}

class NotFoundScreen extends StatelessWidget {
  const NotFoundScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ClientShell(
      child: PageScroll(maxWidth: 640, children: [
        Text("This page doesn't exist", style: text.displaySmall),
        const SizedBox(height: Space.lg),
        Text(
          'The link may be mistyped, or the business may have changed its booking address.',
          style: text.bodyLarge?.copyWith(color: Palette.muted),
        ),
        const SizedBox(height: Space.xl),
        FilledButton(onPressed: () => context.go('/search'), child: const Text('Search for a business')),
      ]),
    );
  }
}
