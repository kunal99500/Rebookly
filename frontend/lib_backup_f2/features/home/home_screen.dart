import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../shared/brand.dart';
import '../../shared/categories.dart';
import '../../shared/client_shell.dart';
import '../../shared/hold_ticket.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';

/// The front door: search for a place, see what a booking looks like, or set up a business.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= Breakpoints.wide;
    return ClientShell(
      child: SingleChildScrollView(
        child: Column(children: [
          _Hero(wide: wide),
          _HowItWorks(wide: wide),
          _ForBusinesses(wide: wide),
          const _Footer(),
        ]),
      ),
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.wide});

  final bool wide;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final copy = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(
        'Book the time.\nHold a little.\nPay at the visit.',
        style: (wide ? text.displayLarge : text.displayMedium)?.copyWith(fontSize: wide ? 68 : 44),
      ),
      const SizedBox(height: Space.xl),
      ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Text(
          'Find barbers, salons, tutors and trainers near you. A small deposit holds your booking, '
          'goes toward your bill when you arrive, and the cancellation rules are clear before you pay.',
          style: text.bodyLarge?.copyWith(color: Palette.muted, fontSize: 17),
        ),
      ),
      const SizedBox(height: Space.xxl),
      const _SearchBox(),
      const SizedBox(height: Space.lg),
      Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
        for (final category in featuredCategories)
          ActionChip(
            label: Text(categoryLabels[category]!),
            onPressed: () => context.go('/search?category=$category'),
          ),
      ]),
    ]);

    // The one bold gesture on the page: the example ticket sits at a slight angle, like one handed over a counter.
    final ticket = Transform.rotate(
      angle: wide ? -0.025 : 0,
      child: _TicketExample(animate: !reduceMotion(context)),
    );

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: Breakpoints.page),
        child: Padding(
          padding: EdgeInsets.fromLTRB(wide ? 40 : 20, wide ? 72 : 32, wide ? 40 : 20, wide ? 88 : 48),
          child: wide
              ? Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                  Expanded(flex: 11, child: copy),
                  const SizedBox(width: 64),
                  Expanded(flex: 9, child: ticket),
                ])
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  copy,
                  const SizedBox(height: 48),
                  ticket,
                ]),
        ),
      ),
    );
  }
}

class _SearchBox extends StatefulWidget {
  const _SearchBox();

  @override
  State<_SearchBox> createState() => _SearchBoxState();
}

class _SearchBoxState extends State<_SearchBox> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _search() {
    final query = _controller.text.trim();
    context.go(query.isEmpty ? '/search' : '/search?q=${Uri.encodeQueryComponent(query)}');
  }

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 560),
      child: Row(children: [
        Expanded(
          child: TextField(
            controller: _controller,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _search(),
            decoration: const InputDecoration(
              hintText: 'Haircut, yoga or a place name',
              prefixIcon: Icon(Icons.search_rounded, color: Palette.muted),
            ),
          ),
        ),
        const SizedBox(width: Space.sm),
        FilledButton(onPressed: _search, child: const Text('Search')),
      ]),
    );
  }
}

/// The hero's one orchestrated moment: an example booking ticket slides into its tray.
class _TicketExample extends StatelessWidget {
  const _TicketExample({required this.animate});

  final bool animate;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final tray = DecoratedBox(
      decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.sheet)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 22),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const StatusPill('Held, not charged', state: MoneyState.held),
            const Spacer(),
            Text('Example booking', style: text.bodySmall),
          ]),
          const SizedBox(height: Space.lg),
          const HoldTicket(
            title: 'Haircut and beard trim',
            lines: ["Ravi's Barbershop, Bandra West", 'Tuesday 18 November, 4:30 PM'],
            held: '₹80.00',
            payLater: '₹370.00',
            steps: [
              PolicyStep(label: 'Free to cancel', detail: 'Until Mon, 4:30 PM', state: MoneyState.released, flex: 3),
              PolicyStep(label: 'Late', detail: 'Up to ₹40 kept', state: MoneyState.waiting, flex: 2),
              PolicyStep(label: 'Missed', detail: 'Up to ₹80 kept', state: MoneyState.problem, flex: 2),
            ],
            footnote: 'If someone else books the time you free up, a late fee is dropped.',
          ),
        ]),
      ),
    );
    if (!animate) return tray;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 900),
      curve: Curves.easeOutCubic,
      builder: (context, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, 28 * (1 - t)), child: child),
      ),
      child: tray,
    );
  }
}

class _HowItWorks extends StatelessWidget {
  const _HowItWorks({required this.wide});

  final bool wide;

  static const _steps = [
    (
      title: "Pick a time that's really free",
      body: "Times come straight from the business's diary, so whatever you see can be booked.",
    ),
    (
      title: 'Hold a small deposit',
      body: "It's held on your card or PayPal, not charged. You see the exact amount and rules first.",
    ),
    (
      title: 'Arrive, or change plans fairly',
      body: "The deposit goes toward your bill. Cancel in time and it's released in full.",
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final steps = [
      for (var i = 0; i < _steps.length; i++)
        _Step(number: i + 1, title: _steps[i].title, body: _steps[i].body),
    ];
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: Palette.surface,
        border: Border.symmetric(horizontal: BorderSide(color: Palette.line)),
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: Breakpoints.page),
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: wide ? 40 : 20, vertical: wide ? 72 : 48),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('How a booking works', style: text.displaySmall),
              const SizedBox(height: Space.xxl),
              if (wide)
                Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  for (var i = 0; i < steps.length; i++) ...[
                    if (i > 0) const SizedBox(width: 40),
                    Expanded(child: steps[i]),
                  ],
                ])
              else
                Column(children: [
                  for (final step in steps) Padding(padding: const EdgeInsets.only(bottom: Space.xl), child: step),
                ]),
            ]),
          ),
        ),
      ),
    );
  }
}

class _Step extends StatelessWidget {
  const _Step({required this.number, required this.title, required this.body});

  final int number;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('$number', style: text.displayMedium?.copyWith(color: Palette.sageDeep, height: 1)),
      const SizedBox(height: Space.md),
      Text(title, style: text.titleLarge),
      const SizedBox(height: Space.sm),
      Text(body, style: text.bodyLarge?.copyWith(color: Palette.muted)),
    ]);
  }
}

class _ForBusinesses extends StatelessWidget {
  const _ForBusinesses({required this.wide});

  final bool wide;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    const promises = [
      'Describe your business in a sentence; Rebookly drafts your services, prices and policy',
      'Deposits are held on the client\'s card, not charged, and go to your own PayPal',
      'You approve every fee, and a late fee is dropped if the time is rebooked',
    ];
    final pitch = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Run your diary with fewer no-shows.', style: text.displaySmall?.copyWith(color: Colors.white)),
      const SizedBox(height: Space.lg),
      Text(
        'For barbers, salons, studios, tutors and trainers who are tired of empty chairs.',
        style: text.bodyLarge?.copyWith(color: Palette.sageDeep),
      ),
      const SizedBox(height: Space.xxl),
      Wrap(spacing: Space.md, runSpacing: Space.md, children: [
        FilledButton(
          onPressed: () => context.go('/business/start'),
          style: FilledButton.styleFrom(backgroundColor: Colors.white, foregroundColor: Palette.forestDeep),
          child: const Text('Set up my business'),
        ),
        OutlinedButton(
          onPressed: () => context.go('/business/signin'),
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.white,
            side: const BorderSide(color: Color(0x66FFFFFF), width: 1.2),
          ),
          child: const Text('Sign in to my business'),
        ),
      ]),
    ]);
    final list = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final promise in promises)
        Padding(
          padding: const EdgeInsets.only(bottom: Space.lg),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Padding(
              padding: EdgeInsets.only(top: 2),
              child: Icon(Icons.check_rounded, color: Colors.white, size: 20),
            ),
            const SizedBox(width: Space.md),
            Expanded(child: Text(promise, style: text.bodyLarge?.copyWith(color: Colors.white))),
          ]),
        ),
    ]);
    return ColoredBox(
      color: Palette.forestDeep,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: Breakpoints.page),
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: wide ? 40 : 20, vertical: wide ? 80 : 52),
            child: wide
                ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(child: pitch),
                    const SizedBox(width: 64),
                    Expanded(child: Padding(padding: const EdgeInsets.only(top: 8), child: list)),
                  ])
                : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    pitch,
                    const SizedBox(height: 40),
                    list,
                  ]),
          ),
        ),
      ),
    );
  }
}

class _Footer extends StatelessWidget {
  const _Footer();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: Breakpoints.page),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 32, 20, 40),
          child: Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: Space.xl,
            runSpacing: Space.md,
            children: [
              const BrandMark(),
              Text('Deposits are held by PayPal and only charged under the rules you agreed to.', style: text.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}
