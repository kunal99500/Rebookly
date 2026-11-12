import 'package:flutter/material.dart';

import '../../app/tokens.dart';

/// Sign-in pages: the form on the left, and on wide screens a calm brand panel on the right.
class AuthLayout extends StatelessWidget {
  const AuthLayout({super.key, required this.child, required this.aside});

  final Widget child;
  final Widget aside;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    final form = SingleChildScrollView(
      padding: EdgeInsets.symmetric(horizontal: wide ? 56 : 20, vertical: wide ? 48 : 28),
      child: Align(
        alignment: wide ? Alignment.centerLeft : Alignment.topCenter,
        child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 420), child: child),
      ),
    );
    return Scaffold(
      body: SafeArea(
        child: wide
            ? Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Expanded(flex: 5, child: Center(child: form)),
                Expanded(
                  flex: 4,
                  child: Container(
                    margin: const EdgeInsets.all(Space.lg),
                    padding: const EdgeInsets.all(48),
                    decoration: BoxDecoration(color: Palette.forestDeep, borderRadius: BorderRadius.circular(Radii.sheet)),
                    child: aside,
                  ),
                ),
              ])
            : form,
      ),
    );
  }
}

class AuthError extends StatelessWidget {
  const AuthError(this.message, {super.key});

  final String message;

  @override
  Widget build(BuildContext context) => Semantics(
        liveRegion: true,
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.error_outline_rounded, color: Palette.problem, size: 18),
          const SizedBox(width: Space.sm),
          Expanded(
            child: Text(message, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Palette.problem)),
          ),
        ]),
      );
}
