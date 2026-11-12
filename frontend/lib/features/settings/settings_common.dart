import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/owner_shell.dart';
import '../owner/owner_data.dart';

Map<String, dynamic> asMap(Object? json) => Map<String, dynamic>.from(json as Map);
List<Map<String, dynamic>> asList(Object? json) => [for (final item in (json as List? ?? const [])) asMap(item)];

/// The owner's (first) business, with everything the settings pages read.
final businessDetailProvider = FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  return asMap(await ref.watch(apiClientProvider).get('/api/owner/businesses/$id'));
});

/// A settings page: finds the owner's business, then builds the page for it.
class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key, required this.title, required this.subtitle, required this.builder, this.maxWidth = 820});

  final String title;
  final String subtitle;
  final double maxWidth;
  final Widget Function(BuildContext context, String businessId, Map<String, dynamic> business) builder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return OwnerShell(
      title: title,
      child: AsyncView<List<OwnedBusiness>>(
        value: ref.watch(ownedBusinessesProvider),
        page: true,
        onRetry: () => ref.invalidate(ownedBusinessesProvider),
        data: (list) {
          if (list.isEmpty) {
            return PageScroll(children: [
              EmptyState(
                icon: Icons.storefront_outlined,
                title: 'Set up your business first',
                message: 'Describe your business and we’ll draft everything for you to check.',
                action: FilledButton(onPressed: () => context.go('/business/start'), child: const Text('Start')),
              ),
            ]);
          }
          final id = list.first.id;
          return AsyncView<Map<String, dynamic>>(
            value: ref.watch(businessDetailProvider(id)),
            page: true,
            onRetry: () => ref.invalidate(businessDetailProvider(id)),
            data: (business) => PageScroll(maxWidth: maxWidth, children: [
              Text(title, style: text.displaySmall),
              const SizedBox(height: Space.sm),
              Text(subtitle, style: text.bodyLarge?.copyWith(color: Palette.muted)),
              const SizedBox(height: Space.xl),
              builder(context, id, business),
            ]),
          );
        },
      ),
    );
  }
}

/// Runs a save, shows the backend's message on failure, and a short confirmation on success.
Future<bool> runSave(BuildContext context, Future<void> Function() action, {String done = 'Saved.'}) async {
  try {
    await action();
    if (context.mounted) showMessage(context, done);
    return true;
  } on ApiException catch (problem) {
    if (context.mounted) {
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Not saved'),
          content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(problem.message),
            for (final detail in problem.details.where((d) => d != problem.message))
              Padding(padding: const EdgeInsets.only(top: 6), child: Text('• $detail')),
          ]),
          actions: [FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('OK'))],
        ),
      );
    }
    return false;
  }
}

/// A primary button that shows a spinner while its action runs.
class BusyButton extends StatefulWidget {
  const BusyButton({super.key, required this.label, required this.onPressed, this.icon});

  final String label;
  final Future<void> Function()? onPressed;
  final IconData? icon;

  @override
  State<BusyButton> createState() => _BusyButtonState();
}

class _BusyButtonState extends State<BusyButton> {
  bool _busy = false;

  Future<void> _run() async {
    setState(() => _busy = true);
    try {
      await widget.onPressed!();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final child = _busy
        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
        : Text(widget.label);
    final onPressed = _busy || widget.onPressed == null ? null : _run;
    return widget.icon == null
        ? FilledButton(onPressed: onPressed, child: child)
        : FilledButton.icon(onPressed: onPressed, icon: Icon(widget.icon, size: 20), label: child);
  }
}

String clock(Object? value) {
  final text = '${value ?? ''}';
  return text.length >= 5 ? text.substring(0, 5) : text;
}
