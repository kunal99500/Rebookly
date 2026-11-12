import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/api/api_exception.dart';
import '../../core/auth/auth_service.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import 'account_data.dart';

/// Your name, your phone (masked), an optional email for reminders, signing out, and deleting your data.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authServiceProvider);
    return ClientShell(
      child: PageScroll(maxWidth: 680, children: [
        const PageTitle('Your profile'),
        AsyncView<ClientProfile?>(
          value: ref.watch(profileProvider),
          onRetry: () => ref.invalidate(profileProvider),
          data: (profile) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _NameSection(profile: profile, phone: auth.clientPhone),
            if (profile != null) ...[
              const SizedBox(height: 40),
              _EmailSection(profile: profile),
            ],
          ]),
        ),
        const SizedBox(height: 40),
        OutlinedButton.icon(
          onPressed: () async {
            await ref.read(authServiceProvider).signOutClient();
            if (context.mounted) context.go('/');
          },
          icon: const Icon(Icons.logout_rounded, size: 20),
          label: const Text('Sign out'),
        ),
        const SizedBox(height: 56),
        const _DeleteSection(),
      ]),
    );
  }
}

class _NameSection extends ConsumerStatefulWidget {
  const _NameSection({required this.profile, required this.phone});

  final ClientProfile? profile;
  final String? phone;

  @override
  ConsumerState<_NameSection> createState() => _NameSectionState();
}

class _NameSectionState extends ConsumerState<_NameSection> {
  late final _name = TextEditingController(text: widget.profile?.name ?? '');
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    if (name.isEmpty) return;
    setState(() => _busy = true);
    try {
      await ref.read(accountApiProvider).saveName(name);
      ref.invalidate(profileProvider);
      if (mounted) showMessage(context, 'Saved.');
    } on ApiException catch (problem) {
      if (mounted) showMessage(context, problem.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader('You', subtitle: 'Businesses see your name, and only the last 4 digits of your phone.'),
      if (widget.profile == null)
        Padding(
          padding: const EdgeInsets.only(bottom: Space.md),
          child: Text('Add your name to start booking.', style: text.bodyMedium?.copyWith(color: Palette.waiting)),
        ),
      TextField(
        controller: _name,
        textCapitalization: TextCapitalization.words,
        maxLength: 80,
        decoration: const InputDecoration(labelText: 'Your name', counterText: ''),
        onSubmitted: (_) => _save(),
      ),
      const SizedBox(height: Space.md),
      Row(children: [
        const Icon(Icons.phone_iphone_rounded, size: 18, color: Palette.muted),
        const SizedBox(width: Space.sm),
        Expanded(
          child: Text(widget.profile?.phoneMasked ?? widget.phone ?? 'No phone number', style: text.bodyMedium),
        ),
        FilledButton(onPressed: _busy ? null : _save, child: const Text('Save')),
      ]),
    ]);
  }
}

class _EmailSection extends ConsumerStatefulWidget {
  const _EmailSection({required this.profile});

  final ClientProfile profile;

  @override
  ConsumerState<_EmailSection> createState() => _EmailSectionState();
}

class _EmailSectionState extends ConsumerState<_EmailSection> {
  final _email = TextEditingController();
  final _code = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action, {String? done}) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
      ref.invalidate(profileProvider);
      if (done != null && mounted) showMessage(context, done);
    } on ApiException catch (problem) {
      if (mounted) setState(() => _error = problem.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final api = ref.read(accountApiProvider);
    final profile = widget.profile;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader('Email for reminders', subtitle: 'Optional. Confirmations, reminders and receipts by email.'),
      if (profile.email != null) ...[
        Row(children: [
          const Icon(Icons.mark_email_read_outlined, color: Palette.released),
          const SizedBox(width: Space.sm),
          Expanded(child: Text(profile.email!, style: text.bodyLarge)),
          TextButton(
            onPressed: _busy ? null : () => _run(api.removeEmail, done: 'Email removed.'),
            child: const Text('Remove'),
          ),
        ]),
      ] else if (profile.emailPending != null) ...[
        Text('We sent a 6-digit code to ${profile.emailPending}.', style: text.bodyMedium),
        const SizedBox(height: Space.md),
        Row(children: [
          Expanded(
            child: TextField(
              controller: _code,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
              decoration: const InputDecoration(labelText: '6-digit code'),
            ),
          ),
          const SizedBox(width: Space.sm),
          FilledButton(
            onPressed: _busy ? null : () => _run(() => api.verifyEmail(_code.text.trim()), done: 'Email confirmed.'),
            child: const Text('Confirm'),
          ),
        ]),
      ] else ...[
        Row(children: [
          Expanded(
            child: TextField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              decoration: const InputDecoration(labelText: 'Email'),
            ),
          ),
          const SizedBox(width: Space.sm),
          FilledButton(
            onPressed: _busy ? null : () => _run(() => api.addEmail(_email.text.trim())),
            child: const Text('Send code'),
          ),
        ]),
      ],
      if (_error != null) ...[
        const SizedBox(height: Space.sm),
        Text(_error!, style: text.bodyMedium?.copyWith(color: Palette.problem)),
      ],
    ]);
  }
}

class _DeleteSection extends ConsumerWidget {
  const _DeleteSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return Panel(
      color: Palette.problemBg,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Delete my data', style: text.titleMedium?.copyWith(color: Palette.problem)),
        const SizedBox(height: Space.sm),
        Text(
          'Removes your name, phone, email, reviews and waitlist. Businesses keep the booking and payment records the law requires.',
          style: text.bodyMedium,
        ),
        const SizedBox(height: Space.md),
        OutlinedButton(
          onPressed: () => _start(context, ref),
          style: OutlinedButton.styleFrom(foregroundColor: Palette.problem, backgroundColor: Palette.surface),
          child: const Text('Delete my data'),
        ),
      ]),
    );
  }

  Future<void> _start(BuildContext context, WidgetRef ref) async {
    DeletionCheck check;
    try {
      check = await ref.refresh(deletionCheckProvider.future);
    } on ApiException catch (problem) {
      if (context.mounted) showMessage(context, problem.message);
      return;
    }
    if (!context.mounted) return;
    if (!check.canDelete) {
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Not just yet'),
          content: Text(check.reasons.join('\n\n')),
          actions: [FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('OK'))],
        ),
      );
      return;
    }
    final typed = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete your data?'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(check.whatHappens),
          const SizedBox(height: Space.lg),
          const Text('Type DELETE to confirm. This can’t be undone.'),
          const SizedBox(height: Space.sm),
          TextField(controller: typed, autofocus: true),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Keep my data')),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(typed.text.trim() == 'DELETE'),
            style: FilledButton.styleFrom(backgroundColor: Palette.problem),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(accountApiProvider).deleteMyData();
      await ref.read(authServiceProvider).signOutClient();
      if (context.mounted) {
        context.go('/');
        showMessage(context, 'Your data has been deleted.');
      }
    } on ApiException catch (problem) {
      if (context.mounted) showMessage(context, problem.message);
    }
  }
}
