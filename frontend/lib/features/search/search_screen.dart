import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/format/money.dart';
import '../../shared/categories.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import 'search_data.dart';

/// Find live businesses by what you type ("barber shop", "beard trim", a name) and by category.
/// The search words and category live in the address, so a search can be shared or bookmarked.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key, this.text = '', this.category});

  final String text;
  final String? category;

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  late final _controller = TextEditingController(text: widget.text);

  @override
  void didUpdateWidget(covariant SearchScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.text != widget.text && _controller.text != widget.text) _controller.text = widget.text;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _go({String? text, String? category, bool clearCategory = false}) {
    final query = <String, String>{
      if ((text ?? _controller.text).trim().isNotEmpty) 'q': (text ?? _controller.text).trim(),
      if (!clearCategory && (category ?? widget.category) != null) 'category': (category ?? widget.category)!,
    };
    context.go(Uri(path: '/search', queryParameters: query.isEmpty ? null : query).toString());
  }

  @override
  Widget build(BuildContext context) {
    final hasQuery = widget.text.isNotEmpty || widget.category != null;
    final SearchQuery query = (text: widget.text, category: widget.category);
    final text = Theme.of(context).textTheme;

    return ClientShell(
      child: PageScroll(maxWidth: 880, children: [
        Text(
          widget.category != null && widget.text.isEmpty ? categoryLabels[widget.category] ?? 'Explore' : 'Explore',
          style: text.displaySmall,
        ),
        const SizedBox(height: Space.xl),
        TextField(
          controller: _controller,
          textInputAction: TextInputAction.search,
          onSubmitted: (_) => _go(),
          decoration: InputDecoration(
            hintText: 'Haircut, yoga or a place name',
            prefixIcon: const Icon(Icons.search_rounded, color: Palette.muted),
            suffixIcon: IconButton(
              tooltip: 'Search',
              icon: const Icon(Icons.arrow_forward_rounded),
              onPressed: _go,
            ),
          ),
        ),
        const SizedBox(height: Space.lg),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(children: [
            for (final category in featuredCategories)
              Padding(
                padding: const EdgeInsets.only(right: Space.sm),
                child: FilterChip(
                  label: Text(categoryLabels[category]!),
                  selected: widget.category == category,
                  showCheckmark: false,
                  onSelected: (selected) =>
                      selected ? _go(category: category) : _go(clearCategory: true),
                ),
              ),
          ]),
        ),
        const SizedBox(height: Space.xxl),
        if (!hasQuery)
          const EmptyState(
            icon: Icons.storefront_outlined,
            title: 'What are you looking for?',
            message: 'Search for a service like "haircut" or "yoga class", a business name, or pick a category above.',
          )
        else
          AsyncView<SearchResults>(
            value: ref.watch(searchProvider(query)),
            onRetry: () => ref.invalidate(searchProvider(query)),
            data: (results) => _Results(results: results, onClear: () => context.go('/search')),
          ),
      ]),
    );
  }
}

class _Results extends StatelessWidget {
  const _Results({required this.results, required this.onClear});

  final SearchResults results;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    if (results.results.isEmpty) {
      return EmptyState(
        icon: Icons.search_off_rounded,
        title: 'No places match that yet',
        message: 'Try a broader word, like "salon" instead of a specific treatment, or clear the category.',
        action: OutlinedButton(onPressed: onClear, child: const Text('Clear search')),
      );
    }
    final count = results.results.length;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('$count ${count == 1 ? 'place' : 'places'}', style: text.bodySmall),
      const SizedBox(height: Space.md),
      for (final result in results.results) _ResultRow(result: result),
    ]);
  }
}

class _ResultRow extends StatelessWidget {
  const _ResultRow({required this.result});

  final SearchResult result;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final where = [
      categorySingular[result.category] ?? 'Local business',
      if (result.city != null) result.city!,
      if (result.distanceKm != null) '${result.distanceKm!.toStringAsFixed(1)} km away',
    ].join(', ');

    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
      child: Material(
        color: Palette.surface,
        borderRadius: BorderRadius.circular(Radii.card),
        child: InkWell(
          borderRadius: BorderRadius.circular(Radii.card),
          onTap: () => context.go('/b/${result.slug}'),
          child: Container(
            padding: const EdgeInsets.all(Space.md),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(Radii.card),
              border: Border.all(color: Palette.line),
            ),
            child: Row(children: [
              _Thumb(url: result.coverThumbUrl, name: result.name),
              const SizedBox(width: Space.lg),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(result.name, style: text.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 2),
                  Text(where, style: text.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 6),
                  _Rating(average: result.ratingAverage, count: result.ratingCount),
                ]),
              ),
              if (result.priceFrom != null) ...[
                const SizedBox(width: Space.md),
                Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Text('from', style: text.bodySmall),
                  Text(
                    formatMoney(result.priceFrom, result.currency, showZeroDecimals: false),
                    style: text.titleMedium?.copyWith(fontFeatures: Fonts.tabular),
                  ),
                ]),
              ],
            ]),
          ),
        ),
      ),
    );
  }
}

class _Thumb extends StatelessWidget {
  const _Thumb({required this.url, required this.name});

  final String? url;
  final String name;

  @override
  Widget build(BuildContext context) {
    final placeholder = Container(
      color: Palette.sage,
      alignment: Alignment.center,
      child: Text(
        name.isEmpty ? '?' : name.characters.first.toUpperCase(),
        style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Palette.forest),
      ),
    );
    return ClipRRect(
      borderRadius: BorderRadius.circular(Radii.control),
      child: SizedBox(
        width: 72,
        height: 72,
        child: url == null
            ? placeholder
            : Image.network(url!, fit: BoxFit.cover, errorBuilder: (_, __, ___) => placeholder),
      ),
    );
  }
}

class _Rating extends StatelessWidget {
  const _Rating({required this.average, required this.count});

  final String? average;
  final int count;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    if (count == 0 || average == null) return Text('New on Rebookly', style: text.labelSmall?.copyWith(color: Palette.forest));
    final value = double.tryParse(average!)?.toStringAsFixed(1) ?? average!;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.star_rounded, size: 16, color: Palette.waiting),
      const SizedBox(width: 3),
      Text(value, style: text.labelMedium),
      const SizedBox(width: 4),
      Text('($count ${count == 1 ? 'review' : 'reviews'})', style: text.bodySmall),
    ]);
  }
}
