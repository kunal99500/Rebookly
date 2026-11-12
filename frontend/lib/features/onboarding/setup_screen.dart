import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/money.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import '../../shared/owner_shell.dart';
import '../owner/owner_data.dart';

/// After onboarding: confirm the cancellation policy, finish the rest, and go live.
class SetupScreen extends ConsumerWidget {
  const SetupScreen({super.key, this.businessId, this.policyVersion});

  final String? businessId;
  final int? policyVersion;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (businessId != null) {
      return OwnerShell(title: 'Get ready to go live', child: _Setup(businessId: businessId!, policyVersion: policyVersion));
    }
    return OwnerShell(
      title: 'Get ready to go live',
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
            : _Setup(businessId: list.first.id, policyVersion: policyVersion),
      ),
    );
  }
}

final _businessDetailProvider = FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  return Map<String, dynamic>.from(await ref.watch(apiClientProvider).get('/api/owner/businesses/$id') as Map);
});

/// The newest policy version that hasn't been confirmed yet, if any.
final _draftPolicyProvider = FutureProvider.autoDispose.family<int?, String>((ref, id) async {
  try {
    final json = await ref.watch(apiClientProvider).get('/api/owner/businesses/$id/policies');
    final drafts = [
      for (final item in (json as List).cast<Map>())
        if (item['confirmed_at'] == null && item['status'] != 'confirmed' && item['is_current'] != true)
          (item['version'] as num).toInt(),
    ]..sort();
    return drafts.isEmpty ? null : drafts.last;
  } on ApiException {
    return null;
  }
});

class _Setup extends ConsumerStatefulWidget {
  const _Setup({required this.businessId, this.policyVersion});

  final String businessId;
  final int? policyVersion;

  @override
  ConsumerState<_Setup> createState() => _SetupState();
}

class _SetupState extends ConsumerState<_Setup> {
  bool _busy = false;
  Object? _goLiveProblem;

  Future<void> _goLive() async {
    setState(() {
      _busy = true;
      _goLiveProblem = null;
    });
    try {
      await ref.read(apiClientProvider).post('/api/owner/businesses/${widget.businessId}/go-live');
      ref.invalidate(_businessDetailProvider(widget.businessId));
      ref.invalidate(ownedBusinessesProvider);
      if (mounted) showMessage(context, 'You’re live. Clients can book now.');
    } catch (error) {
      if (mounted) setState(() => _goLiveProblem = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return AsyncView<Map<String, dynamic>>(
      value: ref.watch(_businessDetailProvider(widget.businessId)),
      page: true,
      onRetry: () => ref.invalidate(_businessDetailProvider(widget.businessId)),
      data: (business) {
        final live = business['status'] == 'live';
        final slug = '${business['slug'] ?? ''}';
        final hasPolicy = business['current_policy_version'] != null;
        final draftVersion = widget.policyVersion ?? ref.watch(_draftPolicyProvider(widget.businessId)).valueOrNull;
        final showPolicy = draftVersion != null && business['current_policy_version'] != draftVersion;

        return PageScroll(maxWidth: 820, children: [
          Text(live ? '${business['name']} is live' : 'Almost there', style: text.displaySmall),
          const SizedBox(height: Space.sm),
          Text(
            live
                ? 'Share your booking link so clients can book.'
                : 'A few things to finish. Required ones are marked; the rest make your page better.',
            style: text.bodyLarge?.copyWith(color: Palette.muted),
          ),
          const SizedBox(height: Space.xl),
          if (live && slug.isNotEmpty) ...[
            _BookingLink(slug: slug),
            const SizedBox(height: Space.xl),
          ],
          if (showPolicy) ...[
            _ConfirmPolicy(businessId: widget.businessId, version: draftVersion, currency: '${business['currency'] ?? 'USD'}'),
            const SizedBox(height: Space.xl),
          ],
          _Item(
            done: hasPolicy,
            mandatory: true,
            title: 'Cancellation policy',
            detail: hasPolicy ? 'Confirmed. Clients see it before they pay.' : 'Confirm your policy above.',
            path: '/business/settings/policy',
          ),
          _Item(
            done: business['city'] != null || business['latitude'] != null,
            title: 'Location',
            detail: 'So nearby clients can find you.',
            path: '/business/settings/location',
          ),
          _Item(
            done: business['description'] != null,
            title: 'Business details',
            detail: 'Name, description, contact email, when clients see the deposit.',
            path: '/business/settings/profile',
          ),
          const _Item(title: 'Opening hours and team', detail: 'Who works when, and which services they do.', path: '/business/settings/team'),
          const _Item(title: 'Photos', detail: 'A cover photo and a few of your place.', path: '/business/settings/photos'),
          const _Item(title: 'Tax details', detail: 'Only if you’re registered, so tax shows on receipts.', path: '/business/settings/tax'),
          _Item(
            done: business['paypal_status'] == 'connected',
            title: 'PayPal',
            detail: 'Deposits go straight to your own PayPal account.',
            path: '/business/settings/paypal',
          ),
          const SizedBox(height: Space.xl),
          if (!live) ...[
            if (_goLiveProblem != null) ...[ErrorPanel(error: _goLiveProblem!), const SizedBox(height: Space.lg)],
            FilledButton.icon(
              onPressed: _busy ? null : _goLive,
              icon: const Icon(Icons.rocket_launch_outlined, size: 20),
              label: const Text('Go live'),
            ),
            const SizedBox(height: Space.sm),
            Text('If something required is missing, we’ll tell you exactly what.', style: text.bodySmall),
          ] else
            OutlinedButton(onPressed: () => context.go('/business'), child: const Text('Go to today')),
        ]);
      },
    );
  }
}

class _BookingLink extends StatelessWidget {
  const _BookingLink({required this.slug});

  final String slug;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final link = '${Uri.base.origin}/b/$slug';
    return Panel(
      color: Palette.releasedBg,
      child: Row(children: [
        const Icon(Icons.link_rounded, color: Palette.released),
        const SizedBox(width: Space.md),
        Expanded(child: Text(link, style: text.titleSmall, overflow: TextOverflow.ellipsis)),
        TextButton(
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: link));
            if (context.mounted) showMessage(context, 'Link copied. Share it on WhatsApp or Instagram.');
          },
          child: const Text('Copy'),
        ),
        TextButton(onPressed: () => context.go('/b/$slug'), child: const Text('Open')),
      ]),
    );
  }
}

class _Item extends StatelessWidget {
  const _Item({required this.title, required this.detail, required this.path, this.done = false, this.mandatory = false});

  final String title;
  final String detail;
  final String path;
  final bool done;
  final bool mandatory;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(children: [
      ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(done ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
            color: done ? Palette.released : (mandatory ? Palette.waiting : Palette.faint)),
        title: Text(mandatory && !done ? '$title (required)' : title, style: text.titleSmall),
        subtitle: Text(detail, style: text.bodySmall),
        trailing: const Icon(Icons.chevron_right_rounded, color: Palette.muted),
        onTap: () => context.go(path),
      ),
      const Divider(),
    ]);
  }
}

class _ConfirmPolicy extends ConsumerStatefulWidget {
  const _ConfirmPolicy({required this.businessId, required this.version, required this.currency});

  final String businessId;
  final int version;
  final String currency;

  @override
  ConsumerState<_ConfirmPolicy> createState() => _ConfirmPolicyState();
}

class _ConfirmPolicyState extends ConsumerState<_ConfirmPolicy> {
  late final Future<dynamic> _preview = ref
      .read(apiClientProvider)
      .get('/api/owner/businesses/${widget.businessId}/policies/${widget.version}/preview');
  bool _busy = false;
  String? _error;

  Future<void> _confirm() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(apiClientProvider).post('/api/owner/businesses/${widget.businessId}/policies/${widget.version}/confirm');
      ref.invalidate(_businessDetailProvider(widget.businessId));
      ref.invalidate(_draftPolicyProvider(widget.businessId));
      if (mounted) showMessage(context, 'Policy confirmed.');
    } on ApiException catch (problem) {
      if (mounted) setState(() => _error = problem.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Panel(
      color: Palette.waitingBg,
      child: FutureBuilder<dynamic>(
        future: _preview,
        builder: (context, snapshot) {
          if (snapshot.hasError) return ErrorPanel(error: snapshot.error!);
          if (!snapshot.hasData) return const SizedBox(height: 120, child: Center(child: CircularProgressIndicator()));
          final preview = Map<String, dynamic>.from(snapshot.data as Map);
          final rows = (preview['rows'] as List? ?? const []).cast<Map>();
          final warnings = [for (final w in (preview['warnings'] as List? ?? const [])) w.toString()];
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const StatusPill('Needs your confirmation', state: MoneyState.waiting),
              const Spacer(),
              Text('Version ${widget.version}', style: text.bodySmall),
            ]),
            const SizedBox(height: Space.md),
            Text('Confirm your cancellation policy', style: text.headlineSmall),
            const SizedBox(height: Space.sm),
            Text('Exactly what happens in each case, for a ${formatMoney(preview['example_hold'], widget.currency)} deposit:',
                style: text.bodyMedium),
            const SizedBox(height: Space.md),
            for (final row in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(child: Text('${row['situation']}', style: text.bodyMedium)),
                  const SizedBox(width: Space.md),
                  Text(withCurrency('${row['outcome']}', widget.currency), style: text.titleSmall),
                ]),
              ),
            for (final warning in warnings)
              Padding(
                padding: const EdgeInsets.only(top: Space.sm),
                child: Text('• $warning', style: text.bodySmall?.copyWith(color: Palette.waiting)),
              ),
            if (_error != null) ...[
              const SizedBox(height: Space.sm),
              Text(_error!, style: text.bodyMedium?.copyWith(color: Palette.problem)),
            ],
            const SizedBox(height: Space.lg),
            Wrap(spacing: Space.md, runSpacing: Space.sm, children: [
              FilledButton(onPressed: _busy ? null : _confirm, child: const Text('Confirm policy')),
              TextButton(onPressed: () => context.go('/business/settings/policy'), child: const Text('Change it first')),
            ]),
          ]);
        },
      ),
    );
  }
}
