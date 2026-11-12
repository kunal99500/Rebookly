import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
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
        aside: _OwnerAside(),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          BrandMark(),
          SizedBox(height: 48),
          Text(context.tr('owner_signin.check_inbox'), style: text.displaySmall),
          SizedBox(height: Space.md),
          Text(
            context.tr('owner_signin.check_inbox_body', {'email': _checkInbox}),
            style: text.bodyLarge?.copyWith(color: Palette.muted),
          ),
          SizedBox(height: Space.xl),
          OutlinedButton(
            onPressed: () => setState(() {
              _checkInbox = null;
              _creating = false;
            }),
            child: Text(context.tr('owner_signin.back')),
          ),
        ]),
      );
    }

    return AuthLayout(
      aside: _OwnerAside(),
      child: Form(
        key: _form,
        child: AutofillGroup(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            BrandMark(),
            SizedBox(height: 48),
            Text(_creating ? context.tr('owner_signin.create_title') : context.tr('owner_signin.title'), style: text.displaySmall),
            SizedBox(height: Space.md),
            Text(
              _creating
                  ? context.tr('owner_signin.create_lead')
                  : context.tr('owner_signin.lead'),
              style: text.bodyLarge?.copyWith(color: Palette.muted),
            ),
            SizedBox(height: Space.xxl),
            TextFormField(
              controller: _email,
              autofocus: true,
              keyboardType: TextInputType.emailAddress,
              autofillHints: [AutofillHints.email],
              textInputAction: TextInputAction.next,
              decoration: InputDecoration(labelText: context.tr('owner_signin.email')),
              validator: (value) {
                final email = value?.trim() ?? '';
                return RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$').hasMatch(email) ? null : context.tr('owner_signin.bad_email');
              },
            ),
            SizedBox(height: Space.md),
            TextFormField(
              controller: _password,
              obscureText: !_showPassword,
              autofillHints: [_creating ? AutofillHints.newPassword : AutofillHints.password],
              textInputAction: TextInputAction.done,
              onFieldSubmitted: (_) => _busy ? null : _submit(),
              decoration: InputDecoration(
                labelText: context.tr('owner_signin.password'),
                helperText: _creating ? context.tr('owner_signin.min8') : null,
                suffixIcon: IconButton(
                  tooltip: _showPassword ? context.tr('owner_signin.hide') : context.tr('owner_signin.show'),
                  icon: Icon(_showPassword ? Icons.visibility_off_outlined : Icons.visibility_outlined),
                  onPressed: () => setState(() => _showPassword = !_showPassword),
                ),
              ),
              validator: (value) {
                final password = value ?? '';
                if (password.isEmpty) return context.tr('owner_signin.need_password');
                if (_creating && password.length < 8) return context.tr('owner_signin.use8');
                return null;
              },
            ),
            if (_error != null) ...[
              SizedBox(height: Space.md),
              AuthError(_error!),
            ],
            SizedBox(height: Space.xl),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _busy ? null : _submit,
                child: _busy
                    ? SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
                    : Text(_creating ? context.tr('owner_signin.create') : context.tr('account.sign_in')),
              ),
            ),
            SizedBox(height: Space.md),
            TextButton(
              onPressed: _busy
                  ? null
                  : () => setState(() {
                        _creating = !_creating;
                        _error = null;
                      }),
              child: Text(_creating ? context.tr('owner_signin.have_account') : context.tr('owner_signin.new')),
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
    final points = [
      context.tr('owner_signin.point1'),
      context.tr('owner_signin.point2'),
      context.tr('owner_signin.point3'),
    ];
    return Column(mainAxisAlignment: MainAxisAlignment.end, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(context.tr('owner_signin.aside_title'), style: text.displaySmall?.copyWith(color: Colors.white)),
      SizedBox(height: Space.xl),
      for (final point in points)
        Padding(
          padding: EdgeInsets.only(bottom: Space.md),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(Icons.check_rounded, color: Colors.white, size: 20),
            SizedBox(width: Space.md),
            Expanded(child: Text(point, style: text.bodyLarge?.copyWith(color: Palette.sageDeep))),
          ]),
        ),
    ]);
  }
}
