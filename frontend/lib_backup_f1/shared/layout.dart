import 'package:flutter/material.dart';

import '../app/tokens.dart';

/// A scrolling page with a comfortable maximum width and responsive side padding.
class PageScroll extends StatelessWidget {
  const PageScroll({
    super.key,
    required this.children,
    this.maxWidth = Breakpoints.page,
    this.padding,
    this.crossAxisAlignment = CrossAxisAlignment.start,
  });

  final List<Widget> children;
  final double maxWidth;
  final EdgeInsets? padding;
  final CrossAxisAlignment crossAxisAlignment;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    return SingleChildScrollView(
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: Padding(
            padding: padding ?? EdgeInsets.fromLTRB(wide ? 40 : 20, wide ? 32 : 20, wide ? 40 : 20, 48),
            child: Column(crossAxisAlignment: crossAxisAlignment, children: children),
          ),
        ),
      ),
    );
  }
}

/// A page title with an optional sentence under it and an optional action on the right.
class PageTitle extends StatelessWidget {
  const PageTitle(this.title, {super.key, this.subtitle, this.action});

  final String title;
  final String? subtitle;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.xl),
      child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: text.displaySmall),
            if (subtitle != null) ...[
              const SizedBox(height: Space.sm),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 620),
                child: Text(subtitle!, style: text.bodyLarge?.copyWith(color: Palette.muted)),
              ),
            ],
          ]),
        ),
        if (action != null) ...[const SizedBox(width: Space.lg), action!],
      ]),
    );
  }
}

/// A section heading inside a page.
class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.subtitle, this.action});

  final String title;
  final String? subtitle;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.md),
      child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: text.headlineSmall),
            if (subtitle != null) ...[
              const SizedBox(height: 4),
              Text(subtitle!, style: text.bodySmall),
            ],
          ]),
        ),
        if (action != null) action!,
      ]),
    );
  }
}

/// A plain white panel with a hairline border, for things that are a distinct object.
class Panel extends StatelessWidget {
  const Panel({super.key, required this.child, this.padding = const EdgeInsets.all(Space.xl), this.color});

  final Widget child;
  final EdgeInsets padding;
  final Color? color;

  @override
  Widget build(BuildContext context) => DecoratedBox(
        decoration: BoxDecoration(
          color: color ?? Palette.surface,
          borderRadius: BorderRadius.circular(Radii.card),
          border: Border.all(color: color == null ? Palette.line : color!),
        ),
        child: Padding(padding: padding, child: child),
      );
}

/// Respect "reduce motion" settings everywhere we animate.
bool reduceMotion(BuildContext context) => MediaQuery.maybeDisableAnimationsOf(context) ?? false;
