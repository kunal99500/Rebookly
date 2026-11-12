import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/owner_shell.dart';
import 'owner_data.dart';

/// The owner's home: today's briefing. New owners are guided to set up their business first.
class OwnerTodayScreen extends ConsumerWidget {
  const OwnerTodayScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final businesses = ref.watch(ownedBusinessesProvider);
    return OwnerShell(
      title: 'Today',
      child: AsyncView<List<OwnedBusiness>>(
        value: businesses,
        page: true,
        loading: const SkeletonList(rows: 3),
        onRetry: () => ref.invalidate(ownedBusinessesProvider),
        data: (list) => list.isEmpty ? const _Welcome() : _Today(business: list.first),
      ),
    );
  }
}

class _Welcome extends StatelessWidget {
  const _Welcome();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return PageScroll(maxWidth: 760, children: [
      Text("Let's set up your business.", style: text.displayMedium),
      const SizedBox(height: Space.lg),
      Text(
        "Tell us what you do in a sentence or two. Rebookly asks a few quick questions, then drafts your services, "
        "prices, opening hours and cancellation policy. You check everything before it's saved.",
        style: text.bodyLarge?.copyWith(color: Palette.muted),
      ),
      const SizedBox(height: Space.xxl),
      FilledButton.icon(
        onPressed: () => context.go('/business/start'),
        icon: const Icon(Icons.auto_awesome_outlined, size: 20),
        label: const Text('Start setting up'),
      ),
      const SizedBox(height: Space.md),
      Text('Takes about five minutes. Nothing goes live until you say so.', style: text.bodySmall),
    ]);
  }
}

class _Today extends ConsumerStatefulWidget {
  const _Today({required this.business});

  final OwnedBusiness business;

  @override
  ConsumerState<_Today> createState() => _TodayState();
}

class _TodayState extends ConsumerState<_Today> {
  Briefing? _refreshed;
  bool _refreshing = false;

  Future<void> _refresh() async {
    setState(() => _refreshing = true);
    try {
      final briefing = await refreshBriefing(ref.read(apiClientProvider), widget.business.id);
      if (mounted) setState(() => _refreshed = briefing);
    } on ApiException catch (problem) {
      if (mounted) showMessage(context, problem.message);
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final briefing = ref.watch(briefingProvider(widget.business.id));
    return PageScroll(maxWidth: 880, children: [
      Row(children: [
        Expanded(child: Text(widget.business.name, style: text.titleMedium?.copyWith(color: Palette.muted))),
        if (!widget.business.isLive)
          TextButton.icon(
            onPressed: () => context.go('/business/setup'),
            icon: const Icon(Icons.rocket_launch_outlined, size: 18),
            label: const Text('Finish setting up'),
          ),
      ]),
      const SizedBox(height: Space.sm),
      AsyncView<Briefing>(
        value: briefing,
        loading: const SkeletonList(rows: 3),
        onRetry: () => ref.invalidate(briefingProvider(widget.business.id)),
        data: (loaded) => _BriefingView(
          briefing: _refreshed ?? loaded,
          refreshing: _refreshing,
          onRefresh: _refresh,
        ),
      ),
    ]);
  }
}

class _BriefingView extends StatelessWidget {
  const _BriefingView({required this.briefing, required this.refreshing, required this.onRefresh});

  final Briefing briefing;
  final bool refreshing;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(briefing.day, style: text.displaySmall),
      const SizedBox(height: Space.lg),
      ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 680),
        child: Text(briefing.summary, style: text.headlineSmall?.copyWith(fontWeight: FontWeight.w500, height: 1.35)),
      ),
      const SizedBox(height: Space.sm),
      Row(children: [
        Text(
          briefing.aiWritten ? 'Summary written by Rebookly AI from the facts below' : 'Summary of the facts below',
          style: text.bodySmall,
        ),
        const Spacer(),
        TextButton.icon(
          onPressed: refreshing || briefing.refreshesLeft == 0 ? null : onRefresh,
          icon: refreshing
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.refresh_rounded, size: 18),
          label: Text(briefing.refreshesLeft == 0 ? 'Refreshed for today' : 'Refresh'),
        ),
      ]),
      const SizedBox(height: Space.xl),
      const Divider(),
      for (final line in briefing.highlights) ...[
        Padding(
          padding: const EdgeInsets.symmetric(vertical: Space.lg),
          child: Text(line, style: text.bodyLarge),
        ),
        const Divider(),
      ],
      if (briefing.suggestions.isNotEmpty) ...[
        const SizedBox(height: Space.xxl),
        Panel(
          color: Palette.sage,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Worth doing today', style: text.titleMedium),
            const SizedBox(height: Space.md),
            for (final tip in briefing.suggestions)
              Padding(
                padding: const EdgeInsets.only(bottom: Space.sm),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 3),
                    child: Icon(Icons.arrow_right_alt_rounded, size: 18, color: Palette.forest),
                  ),
                  const SizedBox(width: Space.sm),
                  Expanded(child: Text(tip, style: text.bodyMedium)),
                ]),
              ),
          ]),
        ),
      ],
    ]);
  }
}
