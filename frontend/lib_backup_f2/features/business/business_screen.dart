import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/format/money.dart';
import '../../core/format/time.dart';
import '../../shared/categories.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'business_data.dart';

/// A business's booking page: what they offer, what it costs, and how cancellations work.
/// This is also the page owners share as their booking link (/b/their-name).
class BusinessScreen extends ConsumerWidget {
  const BusinessScreen({super.key, required this.slug});

  final String slug;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final page = ref.watch(businessPageProvider(slug));
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    final business = page.valueOrNull;

    return ClientShell(
      bottomBar: !wide && business != null ? _MobileBookBar(business: business) : null,
      child: AsyncView<BusinessPage>(
        value: page,
        onRetry: () => ref.invalidate(businessPageProvider(slug)),
        page: true,
        loading: const SkeletonList(rows: 5),
        data: (business) => _BusinessView(business: business, wide: wide),
      ),
    );
  }
}

class _BusinessView extends StatelessWidget {
  const _BusinessView({required this.business, required this.wide});

  final BusinessPage business;
  final bool wide;

  @override
  Widget build(BuildContext context) {
    final details = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _Header(business: business),
      if (business.depositBanner != null) ...[
        const SizedBox(height: Space.xl),
        _DepositBanner(text: business.depositBanner!),
      ],
      const SizedBox(height: 40),
      _ServiceList(
        title: 'Services',
        services: business.mainServices,
        currency: business.currency,
      ),
      if (business.addOns.isNotEmpty) ...[
        const SizedBox(height: Space.xxl),
        _ServiceList(
          title: 'Extras you can add',
          subtitle: 'Added to a main service, in the same visit.',
          services: business.addOns,
          currency: business.currency,
        ),
      ],
      const SizedBox(height: 40),
      _PolicySection(business: business),
      if (business.gallery.isNotEmpty) ...[
        const SizedBox(height: 40),
        _Gallery(business: business),
      ],
    ]);

    return PageScroll(children: [
      _Cover(business: business, wide: wide),
      const SizedBox(height: Space.xl),
      if (wide)
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: details),
          const SizedBox(width: 48),
          SizedBox(width: 340, child: _BookingCard(business: business)),
        ])
      else
        details,
    ]);
  }
}

class _Cover extends StatelessWidget {
  const _Cover({required this.business, required this.wide});

  final BusinessPage business;
  final bool wide;

  @override
  Widget build(BuildContext context) {
    final placeholder = Container(
      color: Palette.sage,
      alignment: Alignment.bottomLeft,
      padding: const EdgeInsets.all(Space.xl),
      child: Text(
        business.name,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.displayLarge?.copyWith(color: Palette.sageDeep, fontSize: wide ? 88 : 56),
      ),
    );
    return ClipRRect(
      borderRadius: BorderRadius.circular(Radii.sheet),
      child: AspectRatio(
        aspectRatio: wide ? 21 / 8 : 4 / 3,
        child: business.cover == null
            ? placeholder
            : Image.network(
                business.cover!.url,
                fit: BoxFit.cover,
                semanticLabel: business.cover!.altText ?? 'Photo of ${business.name}',
                errorBuilder: (_, __, ___) => placeholder,
              ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.business});

  final BusinessPage business;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final average = double.tryParse(business.ratingAverage ?? '');
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(business.name, style: text.displayMedium),
      const SizedBox(height: Space.md),
      Wrap(spacing: Space.lg, runSpacing: Space.sm, crossAxisAlignment: WrapCrossAlignment.center, children: [
        Text(categorySingular[business.category] ?? 'Local business', style: text.titleSmall?.copyWith(color: Palette.forest)),
        if (average != null && business.ratingCount > 0)
          Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.star_rounded, size: 18, color: Palette.waiting),
            const SizedBox(width: 4),
            Text(average.toStringAsFixed(1), style: text.titleSmall),
            const SizedBox(width: 4),
            Text('from ${business.ratingCount} verified ${business.ratingCount == 1 ? 'visit' : 'visits'}', style: text.bodySmall),
          ])
        else
          Text('New on Rebookly', style: text.bodySmall),
        if (business.address != null)
          Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.place_outlined, size: 17, color: Palette.muted),
            const SizedBox(width: 4),
            Text(business.address!, style: text.bodySmall),
          ]),
      ]),
      if (business.description != null && business.description!.isNotEmpty) ...[
        const SizedBox(height: Space.lg),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: Text(business.description!, style: text.bodyLarge),
        ),
      ],
    ]);
  }
}

class _DepositBanner extends StatelessWidget {
  const _DepositBanner({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(Space.lg),
        decoration: BoxDecoration(color: Palette.heldBg, borderRadius: BorderRadius.circular(Radii.card)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(MoneyState.held.icon, color: Palette.held, size: 20),
          const SizedBox(width: Space.md),
          Expanded(
            child: Text(text, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Palette.ink)),
          ),
        ]),
      );
}

class _ServiceList extends StatelessWidget {
  const _ServiceList({required this.title, required this.services, required this.currency, this.subtitle});

  final String title;
  final String? subtitle;
  final List<ServiceItem> services;
  final String currency;

  @override
  Widget build(BuildContext context) {
    if (services.isEmpty) {
      return const EmptyState(
        icon: Icons.content_cut_rounded,
        title: 'No services listed yet',
        message: 'This business is still adding what they offer. Check back soon.',
      );
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionHeader(title, subtitle: subtitle),
      const Divider(),
      for (final service in services) ...[
        _ServiceRow(service: service, currency: currency),
        const Divider(),
      ],
    ]);
  }
}

class _ServiceRow extends StatelessWidget {
  const _ServiceRow({required this.service, required this.currency});

  final ServiceItem service;
  final String currency;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final deposit = num.tryParse(service.deposit) ?? 0;
    final facts = [
      formatDuration(service.durationMinutes),
      if (service.isClass) 'group class',
      if (!service.isAddOn && deposit > 0) '${formatMoney(service.deposit, currency)} deposit held',
    ].join(', ');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Space.lg),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(service.name, style: text.titleMedium),
            const SizedBox(height: 3),
            Text(facts, style: text.bodySmall),
            if (service.description != null && service.description!.isNotEmpty) ...[
              const SizedBox(height: Space.sm),
              Text(service.description!, style: text.bodyMedium?.copyWith(color: Palette.muted)),
            ],
          ]),
        ),
        const SizedBox(width: Space.lg),
        Text(
          service.isAddOn ? '+${formatMoney(service.price, currency)}' : formatMoney(service.price, currency),
          style: text.titleMedium?.copyWith(fontFeatures: Fonts.tabular),
        ),
      ]),
    );
  }
}

class _PolicySection extends StatelessWidget {
  const _PolicySection({required this.business});

  final BusinessPage business;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader(
        'How cancellations work',
        subtitle: 'The same rules apply to everyone, and you see them again before you pay.',
      ),
      Panel(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (business.freeCancelHours > 0)
            Padding(
              padding: const EdgeInsets.only(bottom: Space.md),
              child: StatusPill('Free cancellation up to ${business.freeCancelHours} hours before', state: MoneyState.released),
            ),
          for (final line in business.policyLines)
            Padding(
              padding: const EdgeInsets.only(bottom: Space.sm),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: SizedBox(width: 5, height: 5, child: DecoratedBox(decoration: BoxDecoration(color: Palette.forest, shape: BoxShape.circle))),
                ),
                const SizedBox(width: Space.md),
                Expanded(child: Text(line, style: text.bodyMedium)),
              ]),
            ),
          if (business.ownerNote != null) ...[
            const SizedBox(height: Space.sm),
            Text('A note from ${business.name}: ${business.ownerNote}', style: text.bodySmall),
          ],
        ]),
      ),
    ]);
  }
}

class _Gallery extends StatelessWidget {
  const _Gallery({required this.business});

  final BusinessPage business;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader('Photos', subtitle: 'Real photos of the place, confirmed by the owner.'),
      SizedBox(
        height: 180,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: business.gallery.length,
          separatorBuilder: (_, __) => const SizedBox(width: Space.md),
          itemBuilder: (context, index) {
            final photo = business.gallery[index];
            return ClipRRect(
              borderRadius: BorderRadius.circular(Radii.card),
              child: AspectRatio(
                aspectRatio: (photo.width != null && photo.height != null && photo.height! > 0)
                    ? photo.width! / photo.height!
                    : 4 / 3,
                child: Image.network(
                  photo.thumbUrl,
                  fit: BoxFit.cover,
                  semanticLabel: photo.altText ?? 'Photo of ${business.name}',
                  errorBuilder: (_, __, ___) => const ColoredBox(color: Palette.sage),
                ),
              ),
            );
          },
        ),
      ),
    ]);
  }
}

String? _startingPrice(BusinessPage business) {
  final prices = business.mainServices.map((s) => num.tryParse(s.price)).whereType<num>().toList();
  if (prices.isEmpty) return null;
  prices.sort();
  return formatMoney(prices.first, business.currency, showZeroDecimals: false);
}

/// Desktop: a booking card beside the details.
class _BookingCard extends StatelessWidget {
  const _BookingCard({required this.business});

  final BusinessPage business;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final from = _startingPrice(business);
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (from != null) ...[
          Text('Services from', style: text.bodySmall),
          Text(from, style: text.displaySmall?.copyWith(fontFeatures: Fonts.tabular)),
          const SizedBox(height: Space.lg),
        ],
        Text(
          'Pick your services and a time. You see the exact deposit and rules before you pay anything.',
          style: text.bodyMedium?.copyWith(color: Palette.muted),
        ),
        const SizedBox(height: Space.xl),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: business.mainServices.isEmpty ? null : () => context.go('/b/${business.slug}/book'),
            child: const Text('Book a time'),
          ),
        ),
        const SizedBox(height: Space.md),
        Row(children: [
          Icon(MoneyState.held.icon, size: 16, color: Palette.held),
          const SizedBox(width: 6),
          Expanded(child: Text('Deposits are held, not charged', style: text.bodySmall)),
        ]),
      ]),
    );
  }
}

/// Phones: the booking action stays at the bottom of the screen.
class _MobileBookBar extends StatelessWidget {
  const _MobileBookBar({required this.business});

  final BusinessPage business;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final from = _startingPrice(business);
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: Palette.surface,
        border: Border(top: BorderSide(color: Palette.line)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
          child: Row(children: [
            if (from != null)
              Expanded(
                child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Services from', style: text.bodySmall),
                  Text(from, style: text.titleLarge?.copyWith(fontFeatures: Fonts.tabular)),
                ]),
              )
            else
              const Spacer(),
            FilledButton(
              onPressed: business.mainServices.isEmpty ? null : () => context.go('/b/${business.slug}/book'),
              child: const Text('Book a time'),
            ),
          ]),
        ),
      ),
    );
  }
}
