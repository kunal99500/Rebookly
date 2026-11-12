import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/config.dart';
import '../../core/i18n/i18n.dart';
import '../../shared/brand.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'landing_mockups.dart';
import 'landing_parts.dart';

/// The landing page: hero, the problem, the solution, the no-show shield, pricing and how it works.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _how = GlobalKey();
  final _clients = GlobalKey();
  final _businesses = GlobalKey();
  final _shield = GlobalKey();
  final _pricing = GlobalKey();
  final _features = GlobalKey();

  void _scrollTo(GlobalKey key) {
    final target = key.currentContext;
    if (target == null) return;
    Scrollable.ensureVisible(target,
        duration: reduceMotion(context)
            ? Duration.zero
            : const Duration(milliseconds: 500),
        curve: Curves.easeOutCubic);
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 1020;
    return Scaffold(
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(72),
        child: _Header(
          wide: wide,
          links: [
            ('land.nav.how', _how),
            ('land.nav.clients', _clients),
            ('land.nav.businesses', _businesses),
            ('land.nav.shield', _shield),
            ('land.nav.pricing', _pricing),
            ('land.nav.features', _features),
          ],
          onLink: _scrollTo,
        ),
      ),
      body: SingleChildScrollView(
        child: Column(children: [
          _Hero(
              onClients: () => context.go('/search'),
              onBusinesses: () => context.go('/business/start')),
          const _Problem(),
          _Solution(
              featuresKey: _features,
              clientsKey: _clients,
              businessesKey: _businesses),
          _Shield(key: _shield),
          _Pricing(key: _pricing),
          _HowItWorks(key: _how),
          const _Closing(),
          const _Footer(),
        ]),
      ),
    );
  }
}

// ---------- header ----------

class _Header extends StatelessWidget {
  const _Header(
      {required this.wide, required this.links, required this.onLink});

  final bool wide;
  final List<(String, GlobalKey)> links;
  final ValueChanged<GlobalKey> onLink;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      decoration: const BoxDecoration(
          color: Palette.paper,
          border: Border(bottom: BorderSide(color: Palette.line))),
      child: SafeArea(
        bottom: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1180),
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: wide ? 40 : 16),
              child: Row(children: [
                const BrandMark(),
                const Spacer(),
                if (wide)
                  for (final (key, target) in links)
                    TextButton(
                      onPressed: () => onLink(target),
                      style: TextButton.styleFrom(
                          foregroundColor: Palette.ink,
                          textStyle: text.labelLarge
                              ?.copyWith(fontWeight: FontWeight.w500)),
                      child: Text(context.tr(key)),
                    ),
                const SizedBox(width: Space.sm),
                FilledButton(
                  onPressed: () => context.go('/business/start'),
                  style: FilledButton.styleFrom(minimumSize: const Size(0, 42)),
                  child: Text(context.tr('land.get_started')),
                ),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------- hero ----------

class _Hero extends StatelessWidget {
  const _Hero({required this.onClients, required this.onBusinesses});

  final VoidCallback onClients;
  final VoidCallback onBusinesses;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    final headline = (wide ? text.displayMedium : text.displaySmall)
        ?.copyWith(fontSize: wide ? 46 : 34, height: 1.06);
    final copy =
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Eyebrow(context.tr('land.eyebrow')),
      const SizedBox(height: Space.lg),
      Text.rich(
        TextSpan(children: [
          TextSpan(
              text:
                  '${context.tr('land.title1')}\n${context.tr('land.title2')} '),
          TextSpan(
              text: context.tr('land.title3'),
              style: const TextStyle(color: Palette.forest)),
        ]),
        style: headline,
      ),
      const SizedBox(height: Space.xl),
      Text(context.tr('land.lead'),
          style: text.bodyLarge?.copyWith(color: Palette.muted, fontSize: 18)),
      const SizedBox(height: Space.xxl),
      Wrap(spacing: Space.md, runSpacing: Space.md, children: [
        FilledButton.icon(
          onPressed: onClients,
          iconAlignment: IconAlignment.end,
          icon: const Icon(Icons.arrow_forward_rounded, size: 20),
          label: Text(context.tr('land.find_service')),
        ),
        OutlinedButton(
          onPressed: onBusinesses,
          style: OutlinedButton.styleFrom(
              foregroundColor: Palette.forest,
              side: const BorderSide(color: Palette.forest, width: 1.4)),
          child: Text(context.tr('land.im_owner')),
        ),
      ]),
      const SizedBox(height: 36),
      Wrap(spacing: 28, runSpacing: Space.lg, children: [
        _Promise(
            icon: Icons.calendar_month_outlined,
            title: context.tr('land.p1'),
            body: context.tr('land.p1_body')),
        _Promise(
            icon: Icons.verified_user_outlined,
            title: context.tr('land.p2'),
            body: context.tr('land.p2_body')),
        _Promise(
            icon: Icons.bolt_rounded,
            title: context.tr('land.p3'),
            body: context.tr('land.p3_body')),
      ]),
    ]);
    return Band(
        top: 64,
        bottom: 56,
        child: SideBySide(
            left: copy,
            right: const HeroDevices(),
            leftFlex: 11,
            rightFlex: 9,
            gap: 40));
  }
}

class Eyebrow extends StatelessWidget {
  const Eyebrow(this.label, {super.key, this.onDark = false});

  final String label;
  final bool onDark;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: onDark ? const Color(0x14FFFFFF) : Palette.sage,
          borderRadius: BorderRadius.circular(Radii.chip),
          border: onDark ? Border.all(color: const Color(0x29FFFFFF)) : null,
        ),
        child: Text(label,
            style: Theme.of(context)
                .textTheme
                .labelMedium
                ?.copyWith(color: onDark ? Colors.white : Palette.forest)),
      );
}

class _Promise extends StatelessWidget {
  const _Promise({required this.icon, required this.title, required this.body});

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 220),
      child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                  color: Palette.sage, borderRadius: BorderRadius.circular(12)),
              child: Icon(icon, size: 20, color: Palette.forest),
            ),
            const SizedBox(width: Space.md),
            Flexible(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: text.titleSmall),
                    Text(body, style: text.bodySmall),
                  ]),
            ),
          ]),
    );
  }
}

// ---------- the problem ----------

class _Problem extends StatelessWidget {
  const _Problem();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    return Band(
      top: 56,
      bottom: 40,
      child: Column(children: [
        Eyebrow(context.tr('land.problem')),
        const SizedBox(height: Space.md),
        Text(context.tr('land.problem_title'),
            style: text.displaySmall, textAlign: TextAlign.center),
        const SizedBox(height: 40),
        TwoCards(
          left: _ProblemCard(
            who: context.tr('land.for_clients'),
            whoIcon: Icons.groups_outlined,
            title: context.tr('land.problem_clients_title'),
            points: [
              for (var i = 1; i <= 5; i++) context.tr('land.problem_clients_$i')
            ],
            scene: const ClientScene(),
            sceneColor: Palette.sage,
          ),
          right: _ProblemCard(
            who: context.tr('land.for_businesses'),
            whoIcon: Icons.storefront_outlined,
            title: context.tr('land.problem_business_title'),
            points: [
              for (var i = 1; i <= 5; i++)
                context.tr('land.problem_business_$i')
            ],
            scene: const BusinessScene(),
            sceneColor: Palette.waitingBg,
          ),
        ),
        const SizedBox(height: Space.xl),
        Container(
          padding: EdgeInsets.all(wide ? 28 : 20),
          decoration: BoxDecoration(
              color: Palette.sage, borderRadius: BorderRadius.circular(24)),
          child: Flex(
            direction: wide ? Axis.horizontal : Axis.vertical,
            crossAxisAlignment:
                wide ? CrossAxisAlignment.center : CrossAxisAlignment.start,
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: const BoxDecoration(
                    color: Palette.surface, shape: BoxShape.circle),
                child: const Icon(Icons.auto_awesome_outlined,
                    color: Palette.forest),
              ),
              SizedBox(width: wide ? Space.xl : 0, height: wide ? 0 : Space.lg),
              Text.rich(
                TextSpan(children: [
                  TextSpan(text: '${context.tr('land.bridge1')}\n'),
                  TextSpan(
                      text: context.tr('land.bridge2'),
                      style: const TextStyle(color: Palette.forest)),
                ]),
                style: text.headlineMedium,
              ),
              SizedBox(width: wide ? Space.xl : 0, height: wide ? 0 : Space.md),
              if (wide)
                Container(width: 1, height: 56, color: Palette.sageDeep),
              if (wide) const SizedBox(width: Space.xl),
              wide
                  ? Expanded(
                      child: Text(context.tr('land.bridge_body'),
                          style:
                              text.bodyLarge?.copyWith(color: Palette.muted)))
                  : Text(context.tr('land.bridge_body'),
                      style: text.bodyLarge?.copyWith(color: Palette.muted)),
            ],
          ),
        ),
      ]),
    );
  }
}

/// Two cards side by side on wide screens, stacked on phones, with equal heights.
class TwoCards extends StatelessWidget {
  const TwoCards({super.key, required this.left, required this.right});

  final Widget left;
  final Widget right;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    if (!wide) {
      return Column(children: [left, const SizedBox(height: Space.xl), right]);
    }
    return IntrinsicHeight(
      child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Expanded(child: left),
        const SizedBox(width: Space.xl),
        Expanded(child: right),
      ]),
    );
  }
}

class _Who extends StatelessWidget {
  const _Who(this.label, this.icon);

  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) =>
      Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 18, color: Palette.forest),
        const SizedBox(width: Space.sm),
        Text(label,
            style: Theme.of(context)
                .textTheme
                .labelLarge
                ?.copyWith(color: Palette.forest)),
      ]);
}

class _ProblemCard extends StatelessWidget {
  const _ProblemCard({
    required this.who,
    required this.whoIcon,
    required this.title,
    required this.points,
    required this.scene,
    required this.sceneColor,
  });

  final String who;
  final IconData whoIcon;
  final String title;
  final List<String> points;
  final Widget scene;
  final Color sceneColor;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
          color: Palette.surface,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: Palette.line)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Container(
            color: sceneColor,
            padding: const EdgeInsets.all(24),
            constraints: const BoxConstraints(minHeight: 200),
            child: scene),
        Padding(
          padding: const EdgeInsets.all(26),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _Who(who, whoIcon),
            const SizedBox(height: Space.md),
            Text(title, style: text.headlineMedium),
            const SizedBox(height: Space.lg),
            for (final point in points) _Point(point, good: false),
          ]),
        ),
      ]),
    );
  }
}

class _Point extends StatelessWidget {
  const _Point(this.label, {required this.good});

  final String label;
  final bool good;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 9),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(good ? Icons.check_rounded : Icons.close_rounded,
                size: 19, color: good ? Palette.forest : Palette.problem),
          ),
          const SizedBox(width: Space.sm),
          Expanded(
              child: Text(label,
                  style: Theme.of(context)
                      .textTheme
                      .bodyLarge
                      ?.copyWith(fontSize: 15))),
        ]),
      );
}

// ---------- the solution ----------

class _Solution extends StatelessWidget {
  const _Solution(
      {required this.featuresKey,
      required this.clientsKey,
      required this.businessesKey});

  final GlobalKey featuresKey;
  final GlobalKey clientsKey;
  final GlobalKey businessesKey;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Band(
      key: featuresKey,
      top: 32,
      bottom: 40,
      child: Column(children: [
        Eyebrow(context.tr('land.solution')),
        const SizedBox(height: Space.md),
        Text(context.tr('land.solution_title'),
            style: text.displaySmall, textAlign: TextAlign.center),
        const SizedBox(height: 40),
        TwoCards(
          left: _SolutionCard(
            key: clientsKey,
            who: context.tr('land.for_clients'),
            whoIcon: Icons.phone_iphone_rounded,
            title: context.tr('land.clients_title'),
            body: context.tr('land.clients_body'),
            points: [
              for (var i = 1; i <= 6; i++) context.tr('land.clients_$i')
            ],
            device: const BookingPhone(),
          ),
          right: _SolutionCard(
            key: businessesKey,
            who: context.tr('land.for_businesses'),
            whoIcon: Icons.storefront_outlined,
            title: context.tr('land.business_title'),
            body: context.tr('land.business_body'),
            points: [
              for (var i = 1; i <= 6; i++) context.tr('land.business_$i')
            ],
            device: const AppointmentsLaptop(),
          ),
        ),
      ]),
    );
  }
}

class _SolutionCard extends StatelessWidget {
  const _SolutionCard({
    super.key,
    required this.who,
    required this.whoIcon,
    required this.title,
    required this.body,
    required this.points,
    required this.device,
  });

  final String who;
  final IconData whoIcon;
  final String title;
  final String body;
  final List<String> points;
  final Widget device;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final screen = MediaQuery.sizeOf(context).width;
    final roomy = screen >= 1180 || (screen < Breakpoints.wide && screen > 640);
    final words =
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _Who(who, whoIcon),
      const SizedBox(height: Space.md),
      Text(title, style: text.headlineMedium),
      const SizedBox(height: Space.md),
      Text(body, style: text.bodyLarge?.copyWith(color: Palette.muted)),
      const SizedBox(height: Space.lg),
      for (final point in points) _Point(point, good: true),
    ]);
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
          color: Palette.surface,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: Palette.line)),
      child: roomy
          ? Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
              Expanded(flex: 11, child: words),
              const SizedBox(width: Space.lg),
              Expanded(flex: 9, child: device),
            ])
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [words, const SizedBox(height: Space.xl), device]),
    );
  }
}

// ---------- no-show shield ----------

class _Shield extends StatelessWidget {
  const _Shield({super.key});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 1000;
    final steps = [
      (Icons.calendar_month_outlined, 'land.shield_1', 'land.shield_1_body'),
      (Icons.credit_card_outlined, 'land.shield_2', 'land.shield_2_body'),
      (Icons.swap_horiz_rounded, 'land.shield_3', 'land.shield_3_body'),
      (Icons.check_rounded, 'land.shield_4', 'land.shield_4_body'),
    ];
    final columns = width >= 760 ? 4 : (width >= 420 ? 2 : 1);
    final intro =
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Eyebrow(context.tr('land.shield'), onDark: true),
      const SizedBox(height: Space.lg),
      Text(context.tr('land.shield_title'),
          style:
              text.headlineMedium?.copyWith(color: Colors.white, fontSize: 30)),
      const SizedBox(height: Space.md),
      Text(context.tr('land.shield_body'),
          style: text.bodyLarge?.copyWith(color: Palette.sageDeep)),
    ]);
    final grid = LayoutBuilder(builder: (context, constraints) {
      final itemWidth = (constraints.maxWidth - (columns - 1) * 12) / columns;
      return Wrap(spacing: 12, runSpacing: 12, children: [
        for (final (icon, title, body) in steps)
          SizedBox(
            width: itemWidth,
            child: Container(
              padding: const EdgeInsets.all(18),
              constraints: const BoxConstraints(minHeight: 176),
              decoration: BoxDecoration(
                color: const Color(0x12FFFFFF),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: const Color(0x29FFFFFF)),
              ),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: const BoxDecoration(
                          color: Colors.white, shape: BoxShape.circle),
                      child: Icon(icon, size: 20, color: Palette.forestDeep),
                    ),
                    const SizedBox(height: Space.md),
                    Text(context.tr(title),
                        style: text.titleSmall?.copyWith(color: Colors.white)),
                    const SizedBox(height: 4),
                    Text(context.tr(body),
                        style:
                            text.bodySmall?.copyWith(color: Palette.sageDeep)),
                  ]),
            ),
          ),
      ]);
    });
    return Band(
      top: 16,
      bottom: 40,
      child: Container(
        padding: EdgeInsets.all(wide ? 36 : 24),
        decoration: BoxDecoration(
            color: Palette.forestDeep, borderRadius: BorderRadius.circular(28)),
        child: wide
            ? Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                Expanded(flex: 10, child: intro),
                const SizedBox(width: 32),
                Expanded(flex: 22, child: grid),
              ])
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [intro, const SizedBox(height: Space.xl), grid]),
      ),
    );
  }
}

// ---------- pricing ----------

class _Pricing extends StatelessWidget {
  const _Pricing({super.key});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Band(
      top: 40,
      bottom: 40,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Eyebrow(context.tr('land.pricing.eyebrow')),
        const SizedBox(height: Space.md),
        Text(context.tr('land.pricing.title'),
            style: text.displaySmall, textAlign: TextAlign.center),
        const SizedBox(height: Space.xl),
        TwoCards(
          left: _PlanCard(
            name: context.tr('land.pricing.free.name'),
            price: context.tr('land.pricing.free.price'),
            summary: context.tr('land.pricing.free.fee', {'percent': 3}),
            badge: StatusPill(context.tr('land.pricing.free.badge'),
                state: MoneyState.released),
            points: [
              context.tr('land.pricing.free.point1'),
              context.tr('land.pricing.free.point2'),
              context.tr('land.pricing.free.point3'),
              context.tr('land.pricing.free.point4'),
              context.tr('land.pricing.free.point5'),
            ],
            button: FilledButton(
              onPressed: () => context.go('/business/start'),
              child: Text(context.tr('land.pricing.free.button')),
            ),
          ),
          right: _PlanCard(
            name: context.tr('land.pricing.pro.name'),
            price: context.tr(
                'land.pricing.pro.price', {'price': AppConfig.proPriceLabel}),
            summary: context.tr('land.pricing.pro.summary'),
            points: [
              context.tr('land.pricing.pro.point1'),
              context.tr('land.pricing.pro.point2'),
              context.tr('land.pricing.pro.point3'),
              context.tr('land.pricing.pro.point4'),
            ],
            button: OutlinedButton(
              onPressed: () => context.go('/business/start'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Palette.forest,
                side: const BorderSide(color: Palette.forest),
              ),
              child: Text(context.tr('land.pricing.pro.button')),
            ),
          ),
        ),
        const SizedBox(height: Space.lg),
        Text(context.tr('land.pricing.note.clients'),
            style: text.bodySmall?.copyWith(color: Palette.muted)),
        Text(context.tr('land.pricing.note.deposit'),
            style: text.bodySmall?.copyWith(color: Palette.muted)),
        const SizedBox(height: Space.xl),
        Panel(
          child: Center(
            child: Text(
              context.tr('land.pricing.example'),
              style: text.titleMedium?.copyWith(color: Palette.ink),
              textAlign: TextAlign.center,
            ),
          ),
        ),
        const SizedBox(height: Space.xxl),
        Questions(items: [
          (
            context.tr('land.pricing.faq1.question'),
            context.tr('land.pricing.faq1.answer')
          ),
          (
            context.tr('land.pricing.faq2.question'),
            context.tr('land.pricing.faq2.answer')
          ),
          (
            context.tr('land.pricing.faq3.question'),
            context.tr('land.pricing.faq3.answer')
          ),
          (
            context.tr('land.pricing.faq4.question'),
            context.tr('land.pricing.faq4.answer')
          ),
        ]),
      ]),
    );
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.name,
    required this.price,
    required this.summary,
    required this.points,
    required this.button,
    this.badge,
  });

  final String name;
  final String price;
  final String summary;
  final List<String> points;
  final Widget button;
  final Widget? badge;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: Palette.surface,
        borderRadius: BorderRadius.circular(Radii.sheet),
        border: Border.all(color: Palette.line),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (badge != null) ...[badge!, const SizedBox(height: Space.md)],
        Text(name, style: text.headlineMedium),
        const SizedBox(height: Space.sm),
        Text(price,
            style: text.displaySmall?.copyWith(fontFeatures: Fonts.tabular)),
        const SizedBox(height: Space.sm),
        Text(summary, style: text.bodyLarge?.copyWith(color: Palette.muted)),
        const SizedBox(height: Space.lg),
        for (final point in points) ...[
          _PricingPoint(point),
          const SizedBox(height: Space.md),
        ],
        const SizedBox(height: Space.sm),
        SizedBox(width: double.infinity, child: button),
      ]),
    );
  }
}

class _PricingPoint extends StatelessWidget {
  const _PricingPoint(this.label);

  final String label;

  @override
  Widget build(BuildContext context) => Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.check_rounded, size: 20, color: Palette.forest),
          const SizedBox(width: Space.sm),
          Expanded(
              child:
                  Text(label, style: Theme.of(context).textTheme.bodyMedium)),
        ],
      );
}

// ---------- how it works ----------

class _HowItWorks extends StatelessWidget {
  const _HowItWorks({super.key});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 960;
    final columns = width >= 760 ? 4 : 2;
    final steps = [
      (Icons.search_rounded, 'land.how_1', 'land.how_1_body'),
      (Icons.calendar_month_outlined, 'land.how_2', 'land.how_2_body'),
      (Icons.credit_card_outlined, 'land.how_3', 'land.how_3_body'),
      (Icons.task_alt_rounded, 'land.how_4', 'land.how_4_body'),
    ];
    final intro =
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Eyebrow(context.tr('land.how')),
      const SizedBox(height: Space.md),
      Text(context.tr('land.how_title'),
          style: text.displaySmall?.copyWith(fontSize: 38)),
    ]);
    final grid = LayoutBuilder(builder: (context, constraints) {
      final itemWidth = (constraints.maxWidth - (columns - 1) * 14) / columns;
      return Wrap(spacing: 14, runSpacing: 14, children: [
        for (var i = 0; i < steps.length; i++)
          SizedBox(
            width: itemWidth,
            child: Container(
              padding: const EdgeInsets.all(20),
              constraints: const BoxConstraints(minHeight: 150),
              decoration: BoxDecoration(
                  color: Palette.surface,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Palette.line)),
              child: Stack(children: [
                Positioned(
                    right: 0,
                    top: 0,
                    child: Text('${i + 1}',
                        style: text.headlineMedium
                            ?.copyWith(color: Palette.sageDeep))),
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Icon(steps[i].$1, size: 26, color: Palette.forest),
                  const SizedBox(height: Space.md),
                  Text(context.tr(steps[i].$2), style: text.titleMedium),
                  const SizedBox(height: 4),
                  Text(context.tr(steps[i].$3),
                      style: text.bodyMedium?.copyWith(color: Palette.muted)),
                ]),
              ]),
            ),
          ),
      ]);
    });
    return Band(
      top: 32,
      bottom: 40,
      child: wide
          ? Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
              Expanded(flex: 9, child: intro),
              const SizedBox(width: 32),
              Expanded(flex: 30, child: grid),
            ])
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [intro, const SizedBox(height: Space.xl), grid]),
    );
  }
}

// ---------- closing and footer ----------

class _Closing extends StatelessWidget {
  const _Closing();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    return Band(
      top: 16,
      bottom: 24,
      child: Container(
        padding: EdgeInsets.all(wide ? 44 : 24),
        decoration: BoxDecoration(
            color: Palette.sage, borderRadius: BorderRadius.circular(28)),
        child: Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: Space.xl,
          runSpacing: Space.lg,
          children: [
            Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(context.tr('land.ready'), style: text.displaySmall),
                  const SizedBox(height: Space.sm),
                  Text(context.tr('land.ready_body'),
                      style: text.bodyLarge?.copyWith(color: Palette.muted)),
                ]),
            Wrap(spacing: Space.md, runSpacing: Space.md, children: [
              FilledButton(
                  onPressed: () => context.go('/search'),
                  child: Text(context.tr('land.find_service'))),
              OutlinedButton(
                onPressed: () => context.go('/business/start'),
                style: OutlinedButton.styleFrom(
                    foregroundColor: Palette.forest,
                    side: const BorderSide(color: Palette.forest, width: 1.4)),
                child: Text(context.tr('land.im_owner')),
              ),
            ]),
          ],
        ),
      ),
    );
  }
}

class _Footer extends StatelessWidget {
  const _Footer();

  @override
  Widget build(BuildContext context) => Band(
        top: 24,
        bottom: 40,
        child: Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: Space.xl,
          runSpacing: Space.md,
          children: [
            const BrandMark(),
            Text(context.tr('footer.paypal'),
                style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      );
}
