import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../settings/settings_common.dart';
import 'day_data.dart';
import 'owner_page.dart';

/// Verified reviews from attended visits. Reply publicly, or report one for Rebookly to look at.
class OwnerReviewsScreen extends StatelessWidget {
  const OwnerReviewsScreen({super.key});

  @override
  Widget build(BuildContext context) => OwnerPage(title: 'Reviews', builder: (context, id, business) => _Reviews(businessId: id));
}

class _Reviews extends ConsumerWidget {
  const _Reviews({required this.businessId});

  final String businessId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return PageScroll(maxWidth: 820, children: [
      AsyncView<Map<String, dynamic>>(
        value: ref.watch(ownerReviewsProvider(businessId)),
        onRetry: () => ref.invalidate(ownerReviewsProvider(businessId)),
        data: (page) {
          final summary = asMap(page['summary'] ?? const {});
          final reviews = asList(page['reviews']);
          final average = num.tryParse('${summary['average']}');
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(average == null ? '–' : average.toStringAsFixed(1), style: text.displayMedium),
              const SizedBox(width: Space.md),
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text('from ${summary['count'] ?? 0} verified visits', style: text.bodyLarge?.copyWith(color: Palette.muted)),
              ),
            ]),
            const SizedBox(height: Space.xl),
            if (reviews.isEmpty)
              const EmptyState(icon: Icons.star_outline_rounded, title: 'No reviews yet', message: 'Clients can review a visit after they’ve been checked in.'),
            for (final review in reviews) _Review(review: review, businessId: businessId),
          ]);
        },
      ),
    ]);
  }
}

class _Review extends ConsumerWidget {
  const _Review({required this.review, required this.businessId});

  final Map<String, dynamic> review;
  final String businessId;

  Future<String?> _ask(BuildContext context, String title, String label, String initial, {int min = 1}) {
    final controller = TextEditingController(text: initial);
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SizedBox(
          width: 440,
          child: TextField(controller: controller, autofocus: true, minLines: 2, maxLines: 5, maxLength: 1000, decoration: InputDecoration(labelText: label)),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(controller.text.trim().length >= min ? controller.text.trim() : null),
            child: const Text('Send'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final api = ref.read(apiClientProvider);
    final base = '/api/owner/businesses/$businessId/reviews/${review['id']}';
    void reload() => ref.invalidate(ownerReviewsProvider(businessId));
    final rating = (review['rating'] as num?)?.toInt() ?? 0;
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.md),
      child: Panel(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            for (var i = 1; i <= 5; i++)
              Icon(i <= rating ? Icons.star_rounded : Icons.star_outline_rounded, size: 20, color: i <= rating ? Palette.waiting : Palette.faint),
            const SizedBox(width: Space.sm),
            Expanded(child: Text('${review['reviewer']}, ${review['services']}, ${review['visited_month']}', style: text.bodySmall)),
            if (review['reported'] == true) Text('Reported', style: text.labelSmall?.copyWith(color: Palette.waiting)),
          ]),
          if (review['comment'] != null) ...[const SizedBox(height: Space.sm), Text('${review['comment']}', style: text.bodyLarge)],
          if (review['owner_reply'] != null) ...[
            const SizedBox(height: Space.md),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(Space.md),
              decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.control)),
              child: Text('Your reply: ${review['owner_reply']}', style: text.bodyMedium),
            ),
          ],
          const SizedBox(height: Space.sm),
          Wrap(spacing: Space.sm, children: [
            TextButton(
              onPressed: () async {
                final reply = await _ask(context, 'Reply publicly', 'Your reply', '${review['owner_reply'] ?? ''}');
                if (reply == null || !context.mounted) return;
                if (await runSave(context, () => api.put('$base/reply', body: {'text': reply}), done: 'Reply posted.')) reload();
              },
              child: Text(review['owner_reply'] == null ? 'Reply' : 'Edit reply'),
            ),
            if (review['owner_reply'] != null)
              TextButton(
                onPressed: () async {
                  if (await runSave(context, () => api.delete('$base/reply'), done: 'Reply removed.')) reload();
                },
                child: const Text('Remove reply'),
              ),
            if (review['reported'] != true)
              TextButton(
                style: TextButton.styleFrom(foregroundColor: Palette.muted),
                onPressed: () async {
                  final reason = await _ask(context, 'Report this review', 'Why? (e.g. abusive, not about my business)', '', min: 5);
                  if (reason == null || !context.mounted) return;
                  if (await runSave(context, () => api.post('$base/report', body: {'reason': reason}), done: 'Reported. It stays visible while Rebookly looks at it.')) reload();
                },
                child: const Text('Report'),
              ),
          ]),
        ]),
      ),
    );
  }
}
