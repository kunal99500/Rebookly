import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/i18n/i18n.dart';
import '../app/tokens.dart';
import '../core/auth/auth_service.dart';
import 'brand.dart';
import 'language_button.dart';

typedef NavItem = ({String label, IconData icon, String path});

/// The business owner's workspace: a sidebar on desktop, a bottom bar on phones.
class OwnerShell extends ConsumerWidget {
  const OwnerShell({super.key, required this.title, required this.child, this.actions = const []});

  final String title;
  final Widget child;
  final List<Widget> actions;

  static const List<NavItem> run = [
    (label: 'owner.nav.today', icon: Icons.wb_twilight_rounded, path: '/business'),
    (label: 'owner.nav.bookings', icon: Icons.event_note_outlined, path: '/business/bookings'),
    (label: 'owner.nav.check_in', icon: Icons.qr_code_scanner_rounded, path: '/business/check-in'),
    (label: 'owner.nav.approvals', icon: Icons.fact_check_outlined, path: '/business/approvals'),
    (label: 'owner.nav.classes', icon: Icons.groups_2_outlined, path: '/business/sessions'),
    (label: 'owner.nav.reviews', icon: Icons.star_outline_rounded, path: '/business/reviews'),
  ];

  static const List<NavItem> setUp = [
    (label: 'owner.nav.business', icon: Icons.storefront_outlined, path: '/business/settings/profile'),
    (label: 'owner.nav.services', icon: Icons.content_cut_rounded, path: '/business/settings/services'),
    (label: 'owner.nav.team', icon: Icons.badge_outlined, path: '/business/settings/team'),
    (label: 'owner.nav.policy', icon: Icons.policy_outlined, path: '/business/settings/policy'),
    (label: 'owner.nav.photos', icon: Icons.photo_library_outlined, path: '/business/settings/photos'),
    (label: 'owner.nav.location', icon: Icons.place_outlined, path: '/business/settings/location'),
    (label: 'owner.nav.tax', icon: Icons.receipt_long_outlined, path: '/business/settings/tax'),
    (label: 'owner.nav.paypal', icon: Icons.account_balance_wallet_outlined, path: '/business/settings/paypal'),
    (label: 'owner.nav.plan', icon: Icons.workspace_premium_outlined, path: '/business/settings/plan'),
  ];

  static const List<NavItem> _bottom = [
    (label: 'owner.nav.today', icon: Icons.wb_twilight_rounded, path: '/business'),
    (label: 'owner.nav.bookings', icon: Icons.event_note_outlined, path: '/business/bookings'),
    (label: 'owner.nav.approvals', icon: Icons.fact_check_outlined, path: '/business/approvals'),
    (label: 'owner.nav.set_up', icon: Icons.tune_rounded, path: '/business/settings/profile'),
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
      decoration: BoxDecoration(
        color: Palette.paper,
        border: Border(bottom: BorderSide(color: Palette.line)),
      ),
      child: Row(children: [
        if (!wide) ...[BrandMark(showWordmark: false), SizedBox(width: Space.md)],
        Expanded(child: Text(title, style: text.titleLarge, overflow: TextOverflow.ellipsis)),
        ...actions,
        LanguageButton(),
        SizedBox(width: Space.sm),
        _OwnerAccountButton(),
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
                for (final item in _bottom) NavigationDestination(icon: Icon(item.icon), label: context.tr(item.label)),
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
          padding: EdgeInsets.fromLTRB(12, Space.xl, 12, Space.sm),
          child: Text(label, style: text.labelSmall?.copyWith(color: Palette.muted)),
        );
    return Container(
      width: 252,
      decoration: BoxDecoration(
        color: Palette.surface,
        border: Border(right: BorderSide(color: Palette.line)),
      ),
      child: ListView(padding: EdgeInsets.fromLTRB(16, 18, 16, 24), children: [
        Align(alignment: Alignment.centerLeft, child: BrandMark()),
        group(context.tr('owner.nav.run_the_day')),
        for (final item in OwnerShell.run) _SidebarLink(item: item, active: _isActive(item.path)),
        group(context.tr('owner.nav.set_up')),
        for (final item in OwnerShell.setUp) _SidebarLink(item: item, active: _isActive(item.path)),
        SizedBox(height: Space.xl),
        Divider(),
        SizedBox(height: Space.sm),
        _SidebarLink(item: (label: 'owner.nav.open_site', icon: Icons.open_in_new_rounded, path: '/'), active: false),
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
      padding: EdgeInsets.only(bottom: 2),
      child: Material(
        color: active ? Palette.sage : Colors.transparent,
        borderRadius: BorderRadius.circular(Radii.control),
        child: InkWell(
          borderRadius: BorderRadius.circular(Radii.control),
          onTap: () => context.go(item.path),
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(children: [
              Icon(item.icon, size: 19, color: active ? Palette.forest : Palette.muted),
              SizedBox(width: Space.md),
              Expanded(
                child: Text(
                  context.tr(item.label),
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
      tooltip: auth.email ?? context.tr('account.your_account'),
      position: PopupMenuPosition.under,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.control)),
      onSelected: (value) async {
        if (value == 'signout') {
          await ref.read(authServiceProvider).signOutOwner();
          if (context.mounted) context.go('/');
        } else {
          context.go(value);
        }
      },
      itemBuilder: (context) => [
        if (auth.email != null) PopupMenuItem(enabled: false, child: Text(auth.email!)),
        PopupMenuItem(value: '/', child: Text(context.tr('owner.nav.open_site'))),
        PopupMenuDivider(),
        PopupMenuItem(value: 'signout', child: Text(context.tr('account.sign_out'))),
      ],
      child: CircleAvatar(
        radius: 18,
        backgroundColor: Palette.sage,
        child: Icon(Icons.storefront_rounded, size: 19, color: Palette.forest),
      ),
    );
  }
}
