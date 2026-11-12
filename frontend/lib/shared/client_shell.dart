import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/i18n/i18n.dart';
import '../app/tokens.dart';
import '../core/auth/auth_service.dart';
import 'brand.dart';
import 'language_button.dart';

/// The frame around every client page: a quiet top bar, and a bottom bar on phones.
class ClientShell extends ConsumerWidget {
  const ClientShell({super.key, required this.child, this.bottomBar, this.showNavigation = true});

  final Widget child;
  final Widget? bottomBar;
  final bool showNavigation;

  static const _tabs = [
    (label: 'nav.home', icon: Icons.home_outlined, selectedIcon: Icons.home_rounded, path: '/'),
    (label: 'nav.explore', icon: Icons.search_rounded, selectedIcon: Icons.search_rounded, path: '/search'),
    (label: 'nav.bookings', icon: Icons.event_outlined, selectedIcon: Icons.event_rounded, path: '/my'),
    (label: 'nav.account', icon: Icons.person_outline_rounded, selectedIcon: Icons.person_rounded, path: '/my/profile'),
  ];

  static int _tabFor(String path) {
    if (path.startsWith('/search') || path.startsWith('/b/')) return 1;
    if (path.startsWith('/my/profile')) return 3;
    if (path.startsWith('/my')) return 2;
    return 0;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    final path = GoRouterState.of(context).uri.path;
    final current = _tabFor(path);

    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 68,
        titleSpacing: wide ? 32 : 12,
        title: BrandMark(),
        actions: [
          if (wide && showNavigation) ...[
            _NavLink(label: context.tr('nav.want_to_book'), path: '/for-clients', active: path == '/for-clients'),
            _NavLink(label: context.tr('nav.own_business'), path: '/for-business', active: path == '/for-business'),
            _NavLink(label: context.tr('nav.my_bookings'), path: '/my', active: current == 2),
            SizedBox(width: Space.sm),
          ],
          LanguageButton(),
          _AccountButton(),
          SizedBox(width: wide ? 28 : 8),
        ],
        bottom: PreferredSize(preferredSize: Size.fromHeight(1), child: Divider()),
      ),
      body: SafeArea(top: false, child: child),
      bottomNavigationBar: bottomBar ??
          (wide || !showNavigation
              ? null
              : NavigationBar(
                  selectedIndex: current,
                  onDestinationSelected: (index) => context.go(_tabs[index].path),
                  destinations: [
                    for (final tab in _tabs)
                      NavigationDestination(icon: Icon(tab.icon), selectedIcon: Icon(tab.selectedIcon), label: context.tr(tab.label)),
                  ],
                )),
    );
  }
}

class _NavLink extends StatelessWidget {
  const _NavLink({required this.label, required this.path, required this.active});

  final String label;
  final String path;
  final bool active;

  @override
  Widget build(BuildContext context) => TextButton(
        onPressed: () => context.go(path),
        style: TextButton.styleFrom(foregroundColor: active ? Palette.forest : Palette.ink),
        child: Text(label),
      );
}

class _AccountButton extends ConsumerWidget {
  const _AccountButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authServiceProvider);
    if (!auth.isClientSignedIn) {
      return OutlinedButton(
        onPressed: () => context.go('/signin'),
        style: OutlinedButton.styleFrom(minimumSize: Size(0, 42)),
        child: Text(context.tr('account.sign_in')),
      );
    }
    return PopupMenuButton<String>(
      tooltip: context.tr('account.your_account'),
      position: PopupMenuPosition.under,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.control)),
      onSelected: (value) async {
        if (value == 'signout') {
          await ref.read(authServiceProvider).signOutClient();
          if (context.mounted) context.go('/');
        } else {
          context.go(value);
        }
      },
      itemBuilder: (context) => [
        PopupMenuItem(value: '/my', child: Text(context.tr('nav.my_bookings'))),
        PopupMenuItem(value: '/my/waitlist', child: Text(context.tr('account.waitlist'))),
        PopupMenuItem(value: '/assistant', child: Text(context.tr('account.ask'))),
        PopupMenuItem(value: '/my/profile', child: Text(context.tr('account.profile'))),
        PopupMenuDivider(),
        PopupMenuItem(value: 'signout', child: Text(context.tr('account.sign_out'))),
      ],
      child: CircleAvatar(
        radius: 19,
        backgroundColor: Palette.sage,
        child: Icon(Icons.person_rounded, size: 20, color: Palette.forest),
      ),
    );
  }
}
