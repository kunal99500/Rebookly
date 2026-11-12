import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/auth/auth_service.dart';
import '../../shared/brand.dart';
import 'auth_layout.dart';

/// Business owners sign in with email and password, or create an account.
class OwnerSignInScreen extends ConsumerStatefulWidget {
  const OwnerSignInScreen({super.key});

  @override
  ConsumerState<OwnerSignInScreen> createState() => _OwnerSignInScreenState();
}

class _OwnerSignInScreenState extends ConsumerState<OwnerSignInScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _creating = false;
  bool _busy = false;
  bool _showPassword = false;
  String? _error;
  String? _checkInbox;   // set after creating an account that needs email confirmation

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final auth = ref.read(authServiceProvider);
    final email = _email.text.trim();
    try {
      if (_creating) {
        final signedIn = await auth.createOwnerAccount(email, _password.text);
        if (!signedIn) setState(() => _checkInbox = email);
      } else {
        await auth.signInWithEmail(email, _password.text);
      }
      // When signed in, the router takes the owner on to their business automatically.
    } on AuthFailure catch (failure) {
      setState(() => _error = failure.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;

    if (_checkInbox != null) {
      return AuthLayout(
        aside: const _OwnerAside(),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const BrandMark(),
          const SizedBox(height: 48),
          Text('Check your inbox', style: text.displaySmall),
          const SizedBox(height: Space.md),
          Text(
            'We sent a confirmation link to $_checkInbox. Open it, then come back here and sign in.',
            style: text.bodyLarge?.copyWith(color: Palette.muted),
          ),
          const SizedBox(height: Space.xl),
          OutlinedButton(
            onPressed: () => setState(() {
              _checkInbox = null;
              _creating = false;
            }),
            child: const Text('Back to sign in'),
          ),
        ]),
      );
    }

    return AuthLayout(
      aside: const _OwnerAside(),
      child: Form(
        key: _form,
        child: AutofillGroup(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const BrandMark(),
            const SizedBox(height: 48),
            Text(_creating ? 'Create your business account' : 'Sign in to your business', style: text.displaySmall),
            const SizedBox(height: Space.md),
            Text(
              _creating
                  ? 'Use the email you want booking alerts sent to. You can change it later.'
                  : 'Manage bookings, approve fees and set up your business.',
              style: text.bodyLarge?.copyWith(color: Palette.muted),
            ),
            const SizedBox(height: Space.xxl),
            TextFormField(
              controller: _email,
              autofocus: true,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(labelText: 'Email'),
              validator: (value) {
                final email = value?.trim() ?? '';
                return RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$').hasMatch(email) ? null : 'Enter a valid email address.';
              },
            ),
            const SizedBox(height: Space.md),
            TextFormField(
              controller: _password,
              obscureText: !_showPassword,
              autofillHints: [_creating ? AutofillHints.newPassword : AutofillHints.password],
              textInputAction: TextInputAction.done,
              onFieldSubmitted: (_) => _busy ? null : _submit(),
              decoration: InputDecoration(
                labelText: 'Password',
                helperText: _creating ? 'At least 8 characters.' : null,
                suffixIcon: IconButton(
                  tooltip: _showPassword ? 'Hide password' : 'Show password',
                  icon: Icon(_showPassword ? Icons.visibility_off_outlined : Icons.visibility_outlined),
                  onPressed: () => setState(() => _showPassword = !_showPassword),
                ),
              ),
              validator: (value) {
                final password = value ?? '';
                if (password.isEmpty) return 'Enter your password.';
                if (_creating && password.length < 8) return 'Use at least 8 characters.';
                return null;
              },
            ),
            if (_error != null) ...[
              const SizedBox(height: Space.md),
              AuthError(_error!),
            ],
            const SizedBox(height: Space.xl),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _busy ? null : _submit,
                child: _busy
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
                    : Text(_creating ? 'Create account' : 'Sign in'),
              ),
            ),
            const SizedBox(height: Space.md),
            TextButton(
              onPressed: _busy
                  ? null
                  : () => setState(() {
                        _creating = !_creating;
                        _error = null;
                      }),
              child: Text(_creating ? 'I already have an account' : 'New to Rebookly? Create an account'),
            ),
          ]),
        ),
      ),
    );
  }
}

class _OwnerAside extends StatelessWidget {
  const _OwnerAside();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    const points = [
      'Set up from a short description of your business',
      'Deposits held on the client\'s card, never charged without your say',
      'A daily briefing of what needs you',
    ];
    return Column(mainAxisAlignment: MainAxisAlignment.end, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Fewer empty chairs, and a calmer diary.', style: text.displaySmall?.copyWith(color: Colors.white)),
      const SizedBox(height: Space.xl),
      for (final point in points)
        Padding(
          padding: const EdgeInsets.only(bottom: Space.md),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Icon(Icons.check_rounded, color: Colors.white, size: 20),
            const SizedBox(width: Space.md),
            Expanded(child: Text(point, style: text.bodyLarge?.copyWith(color: Palette.sageDeep))),
          ]),
        ),
    ]);
  }
}
