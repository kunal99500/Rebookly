import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/tokens.dart';
import '../core/api/api_exception.dart';
import 'layout.dart';

/// Loading, error and data for anything fetched from the backend, handled the same way everywhere.
///
/// Set [page] when this is the whole page, so loading and errors get the normal page margins.
class AsyncView<T> extends StatelessWidget {
  const AsyncView({super.key, required this.value, required this.data, this.loading, this.onRetry, this.page = false});

  final AsyncValue<T> value;
  final Widget Function(T data) data;
  final Widget? loading;
  final VoidCallback? onRetry;
  final bool page;

  @override
  Widget build(BuildContext context) => value.when(
        data: data,
        loading: () {
          final placeholder = loading ?? const SkeletonList();
          return page ? PageScroll(children: [placeholder]) : placeholder;
        },
        error: (error, _) {
          final panel = ErrorPanel(error: error, onRetry: onRetry);
          return page ? PageScroll(maxWidth: 760, children: [panel]) : panel;
        },
      );
}

/// What went wrong and what to do about it. Never vague, never apologetic.
class ErrorPanel extends StatelessWidget {
  const ErrorPanel({super.key, required this.error, this.onRetry});

  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final problem = ApiException.from(error);
    final text = Theme.of(context).textTheme;
    return Panel(
      color: Palette.problemBg,
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Icon(Icons.error_outline_rounded, color: Palette.problem),
        const SizedBox(width: Space.md),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(problem.message, style: text.titleSmall?.copyWith(color: Palette.problem)),
            for (final detail in problem.details.where((detail) => detail != problem.message))
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(detail, style: text.bodySmall?.copyWith(color: Palette.ink)),
              ),
            if (onRetry != null) ...[
              const SizedBox(height: Space.md),
              OutlinedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Try again'),
                style: OutlinedButton.styleFrom(minimumSize: const Size(0, 40), backgroundColor: Palette.surface),
              ),
            ],
          ]),
        ),
      ]),
    );
  }
}

/// An empty screen is an invitation to act: say what goes here and what to do next.
class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, required this.message, this.action});

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Space.xxl),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          width: 52,
          height: 52,
          decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.card)),
          child: Icon(icon, color: Palette.forest),
        ),
        const SizedBox(height: Space.lg),
        Text(title, style: text.headlineSmall),
        const SizedBox(height: Space.sm),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Text(message, style: text.bodyLarge?.copyWith(color: Palette.muted)),
        ),
        if (action != null) ...[const SizedBox(height: Space.xl), action!],
      ]),
    );
  }
}

/// Grey placeholder rows that gently pulse while content loads (still when motion is reduced).
class SkeletonList extends StatefulWidget {
  const SkeletonList({super.key, this.rows = 4});

  final int rows;

  @override
  State<SkeletonList> createState() => _SkeletonListState();
}

class _SkeletonListState extends State<SkeletonList> with SingleTickerProviderStateMixin {
  late final AnimationController _pulse =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1100), lowerBound: 0.45, upperBound: 1);

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (reduceMotion(context)) {
      _pulse.stop();
      _pulse.value = 0.7;
    } else if (!_pulse.isAnimating) {
      _pulse.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Loading',
      child: FadeTransition(
        opacity: _pulse,
        child: Column(children: [
          for (var i = 0; i < widget.rows; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: Space.md),
              child: Row(children: [
                _block(width: 64, height: 64),
                const SizedBox(width: Space.lg),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    _block(widthFactor: 0.55, height: 16),
                    const SizedBox(height: Space.sm),
                    _block(widthFactor: 0.35, height: 12),
                  ]),
                ),
              ]),
            ),
        ]),
      ),
    );
  }

  /// A fixed-size block, or (with [widthFactor]) a share of the available width.
  Widget _block({double? width, double? widthFactor, required double height}) {
    final block = Container(
      width: width,
      height: height,
      decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(8)),
    );
    if (widthFactor == null) return block;
    return FractionallySizedBox(widthFactor: widthFactor, alignment: Alignment.centerLeft, child: block);
  }
}

void showMessage(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message)));
}
