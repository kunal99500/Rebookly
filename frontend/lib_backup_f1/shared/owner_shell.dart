import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../app/tokens.dart';
import '../core/auth/auth_service.dart';
import 'brand.dart';

typedef NavItem = ({String label, IconData icon, String path});

/// The business owner's workspace: a sidebar on desktop, a bottom bar on phones.
class OwnerShell extends ConsumerWidget {
  const OwnerShell({super.key, required this.title, required this.child, this.actions = const []});

  final String title;
  final Widget child;
  final List<Widget> actions;

  static const List<NavItem> run = [
    (label: 'Today', icon: Icons.wb_twilight_rounded, path: '/business'),
    (label: 'Bookings', icon: Icons.event_note_outlined, path: '/business/bookings'),
    (label: 'Approvals', icon: Icons.fact_check_outlined, path: '/business/approvals'),
    (label: 'Classes', icon: Icons.groups_2_outlined, path: '/business/sessions'),
    (label: 'Reviews', icon: Icons.star_outline_rounded, path: '/business/reviews'),
  ];

  static const List<NavItem> setUp = [
    (label: 'Business', icon: Icons.storefront_outlined, path: '/business/settings/profile'),
    (label: 'Services', icon: Icons.content_cut_rounded, path: '/business/settings/services'),
    (label: 'Team and hours', icon: Icons.badge_outlined, path: '/business/settings/team'),
    (label: 'Cancellation policy', icon: Icons.policy_outlined, path: '/business/settings/policy'),
    (label: 'Photos', icon: Icons.photo_library_outlined, path: '/business/settings/photos'),
    (label: 'Location', icon: Icons.place_outlined, path: '/business/settings/location'),
    (label: 'Tax', icon: Icons.receipt_long_outlined, path: '/business/settings/tax'),
    (label: 'PayPal', icon: Icons.account_balance_wallet_outlined, path: '/business/settings/paypal'),
  ];

  static const List<NavItem> _bottom = [
    (label: 'Today', icon: Icons.wb_twilight_rounded, path: '/business'),
    (label: 'Bookings', icon: Icons.event_note_outlined, path: '/business/bookings'),
    (label: 'Approvals', icon: Icons.fact_check_outlined, path: '/business/approvals'),
    (label: 'Set up', icon: Icons.tune_rounded, path: '/business/settings/profile'),
  ];

  static int _bottomIndex(String path) {
    if (path.startsWith('/business/bookings')) return 1;
    if (path.startsWith('/business/approvals')) return 2;
    if (path.startsWith('/business/settings') || path.startsWith('/business/setup')) return 3;
    return 0;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.owner;
    final path = GoRouterState.of(context).uri.path;
    final text = Theme.of(context).textTheme;

    final topBar = Container(
      height: 68,
      padding: EdgeInsets.symmetric(horizontal: wide ? 32 : 16),
      decoration: const BoxDecoration(
        color: Palette.paper,
        border: Border(bottom: BorderSide(color: Palette.line)),
      ),
      child: Row(children: [
        if (!wide) ...[const BrandMark(showWordmark: false), const SizedBox(width: Space.md)],
        Expanded(child: Text(title, style: text.titleLarge, overflow: TextOverflow.ellipsis)),
        ...actions,
        const SizedBox(width: Space.sm),
        const _OwnerAccountButton(),
      ]),
    );

    return Scaffold(
      body: SafeArea(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (wide) _Sidebar(path: path),
          Expanded(child: Column(children: [topBar, Expanded(child: child)])),
        ]),
      ),
      bottomNavigationBar: wide
          ? null
          : NavigationBar(
              selectedIndex: _bottomIndex(path),
              onDestinationSelected: (index) => context.go(_bottom[index].path),
              destinations: [
                for (final item in _bottom) NavigationDestination(icon: Icon(item.icon), label: item.label),
              ],
            ),
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.path});

  final String path;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    Widget group(String label) => Padding(
          padding: const EdgeInsets.fromLTRB(12, Space.xl, 12, Space.sm),
          child: Text(label, style: text.labelSmall?.copyWith(color: Palette.muted)),
        );
    return Container(
      width: 252,
      decoration: const BoxDecoration(
        color: Palette.surface,
        border: Border(right: BorderSide(color: Palette.line)),
      ),
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 18, 16, 24), children: [
        const Align(alignment: Alignment.centerLeft, child: BrandMark()),
        group('Run the day'),
        for (final item in OwnerShell.run) _SidebarLink(item: item, active: _isActive(item.path)),
        group('Set up'),
        for (final item in OwnerShell.setUp) _SidebarLink(item: item, active: _isActive(item.path)),
        const SizedBox(height: Space.xl),
        const Divider(),
        const SizedBox(height: Space.sm),
        const _SidebarLink(item: (label: 'Open the booking site', icon: Icons.open_in_new_rounded, path: '/'), active: false),
      ]),
    );
  }

  bool _isActive(String itemPath) => itemPath == '/business' ? path == '/business' : path.startsWith(itemPath);
}

class _SidebarLink extends StatelessWidget {
  const _SidebarLink({required this.item, required this.active});

  final NavItem item;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final color = active ? Palette.forest : Palette.ink;
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Material(
        color: active ? Palette.sage : Colors.transparent,
        borderRadius: BorderRadius.circular(Radii.control),
        child: InkWell(
          borderRadius: BorderRadius.circular(Radii.control),
          onTap: () => context.go(item.path),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(children: [
              Icon(item.icon, size: 19, color: active ? Palette.forest : Palette.muted),
              const SizedBox(width: Space.md),
              Expanded(
                child: Text(
                  item.label,
                  style: text.labelLarge?.copyWith(color: color, fontWeight: active ? FontWeight.w700 : FontWeight.w500),
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

class _OwnerAccountButton extends ConsumerWidget {
  const _OwnerAccountButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authServiceProvider);
    return PopupMenuButton<String>(
      tooltip: auth.email ?? 'Your account',
      position: PopupMenuPosition.under,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.control)),
      onSelected: (value) async {
        if (value == 'signout') {
          await ref.read(authServiceProvider).signOut();
          if (context.mounted) context.go('/');
        } else {
          context.go(value);
        }
      },
      itemBuilder: (context) => [
        if (auth.email != null) PopupMenuItem(enabled: false, child: Text(auth.email!)),
        const PopupMenuItem(value: '/', child: Text('Open the booking site')),
        const PopupMenuDivider(),
        const PopupMenuItem(value: 'signout', child: Text('Sign out')),
      ],
      child: const CircleAvatar(
        radius: 18,
        backgroundColor: Palette.sage,
        child: Icon(Icons.storefront_rounded, size: 19, color: Palette.forest),
      ),
    );
  }
}
