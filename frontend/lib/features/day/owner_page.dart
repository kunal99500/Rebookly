import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/owner_shell.dart';
import '../owner/owner_data.dart';
import '../settings/settings_common.dart';

/// A page in the owner's workspace that needs their business: finds it, then builds the page.
class OwnerPage extends ConsumerWidget {
  const OwnerPage({super.key, required this.title, required this.builder, this.actions = const []});

  final String title;
  final List<Widget> actions;
  final Widget Function(BuildContext context, String businessId, Map<String, dynamic> business) builder;

  @override
  Widget build(BuildContext context, WidgetRef ref) => OwnerShell(
        title: title,
        actions: actions,
        child: AsyncView<List<OwnedBusiness>>(
          value: ref.watch(ownedBusinessesProvider),
          page: true,
          onRetry: () => ref.invalidate(ownedBusinessesProvider),
          data: (list) => list.isEmpty
              ? PageScroll(children: [
                  EmptyState(
                    icon: Icons.storefront_outlined,
                    title: 'Set up your business first',
                    message: 'Describe your business and we’ll draft everything for you to check.',
                    action: FilledButton(onPressed: () => context.go('/business/start'), child: const Text('Start')),
                  ),
                ])
              : AsyncView<Map<String, dynamic>>(
                  value: ref.watch(businessDetailProvider(list.first.id)),
                  page: true,
                  onRetry: () => ref.invalidate(businessDetailProvider(list.first.id)),
                  data: (business) => builder(context, list.first.id, business),
                ),
        ),
      );
}
