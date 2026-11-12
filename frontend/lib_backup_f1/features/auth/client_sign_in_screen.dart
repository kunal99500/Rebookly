import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/auth/auth_service.dart';
import '../../shared/brand.dart';
import 'auth_layout.dart';

/// Clients sign in with their phone: a number, then a 6-digit code. No password to remember.
/// After a successful sign-in the router takes them back to where they were going.
class ClientSignInScreen extends ConsumerStatefulWidget {
  const ClientSignInScreen({super.key});

  @override
  ConsumerState<ClientSignInScreen> createState() => _ClientSignInScreenState();
}

class _ClientSignInScreenState extends ConsumerState<ClientSignInScreen> {
  final _countryCode = TextEditingController(text: '+91');
  final _number = TextEditingController();
  final _code = TextEditingController();
  String? _sentTo;      // the full number a code was sent to
  String? _error;
  bool _busy = false;
  int _resendIn = 0;
  Timer? _timer;

  @override
  void dispose() {
    _countryCode.dispose();
    _number.dispose();
    _code.dispose();
    _timer?.cancel();
    super.dispose();
  }

  String? get _fullNumber {
    final code = _countryCode.text.replaceAll(RegExp(r'[^0-9]'), '');
    final number = _number.text.replaceAll(RegExp(r'[^0-9]'), '');
    if (code.isEmpty || number.length < 6 || number.length > 14) return null;
    return '+$code$number';
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } on AuthFailure catch (failure) {
      setState(() => _error = failure.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _sendCode() async {
    final phone = _fullNumber;
    if (phone == null) {
      setState(() => _error = 'Enter your mobile number, including the country code.');
      return;
    }
    await _run(() async {
      await ref.read(authServiceProvider).sendPhoneCode(phone);
      setState(() {
        _sentTo = phone;
        _code.clear();
      });
      _startResendTimer();
    });
  }

  Future<void> _verify() async {
    final code = _code.text.trim();
    if (code.length != 6) {
      setState(() => _error = 'Enter the 6-digit code from the text message.');
      return;
    }
    // On success the auth state changes and the router moves on by itself.
    await _run(() => ref.read(authServiceProvider).verifyPhoneCode(_sentTo!, code));
  }

  void _startResendTimer() {
    _timer?.cancel();
    setState(() => _resendIn = 30);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return timer.cancel();
      setState(() => _resendIn = _resendIn > 0 ? _resendIn - 1 : 0);
      if (_resendIn == 0) timer.cancel();
    });
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final codeStep = _sentTo != null;

    return AuthLayout(
      aside: const _ClientAside(),
      child: AutofillGroup(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const BrandMark(),
          const SizedBox(height: 48),
          Text(codeStep ? 'Enter your code' : 'Sign in with your phone', style: text.displaySmall),
          const SizedBox(height: Space.md),
          Text(
            codeStep
                ? 'We sent a 6-digit code to $_sentTo. It can take a few seconds to arrive.'
                : "We'll text you a 6-digit code. There's no password to remember.",
            style: text.bodyLarge?.copyWith(color: Palette.muted),
          ),
          const SizedBox(height: Space.xxl),
          if (!codeStep) ...[
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(
                width: 92,
                child: TextField(
                  controller: _countryCode,
                  keyboardType: TextInputType.phone,
                  inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[+0-9]')), LengthLimitingTextInputFormatter(5)],
                  decoration: const InputDecoration(labelText: 'Code'),
                ),
              ),
              const SizedBox(width: Space.sm),
              Expanded(
                child: TextField(
                  controller: _number,
                  autofocus: true,
                  keyboardType: TextInputType.phone,
                  autofillHints: const [AutofillHints.telephoneNumberNational],
                  inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9 ]')), LengthLimitingTextInputFormatter(16)],
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _busy ? null : _sendCode(),
                  decoration: const InputDecoration(labelText: 'Mobile number'),
                ),
              ),
            ]),
          ] else ...[
            TextField(
              controller: _code,
              autofocus: true,
              keyboardType: TextInputType.number,
              autofillHints: const [AutofillHints.oneTimeCode],
              inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _busy ? null : _verify(),
              style: text.headlineMedium?.copyWith(letterSpacing: 10, fontFeatures: Fonts.tabular),
              decoration: const InputDecoration(labelText: '6-digit code', counterText: ''),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: Space.md),
            AuthError(_error!),
          ],
          const SizedBox(height: Space.xl),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _busy ? null : (codeStep ? _verify : _sendCode),
              child: _busy
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
                  : Text(codeStep ? 'Verify and continue' : 'Send code'),
            ),
          ),
          if (codeStep) ...[
            const SizedBox(height: Space.md),
            Wrap(spacing: Space.sm, children: [
              TextButton(
                onPressed: _busy ? null : () => setState(() {
                  _sentTo = null;
                  _error = null;
                }),
                child: const Text('Change number'),
              ),
              TextButton(
                onPressed: _busy || _resendIn > 0 ? null : _sendCode,
                child: Text(_resendIn > 0 ? 'Send again in ${_resendIn}s' : 'Send a new code'),
              ),
            ]),
          ],
          const SizedBox(height: 40),
          Text(
            'Your number is stored encrypted. Businesses only ever see its last 4 digits.',
            style: text.bodySmall,
          ),
        ]),
      ),
    );
  }
}

class _ClientAside extends StatelessWidget {
  const _ClientAside();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(mainAxisAlignment: MainAxisAlignment.end, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(
        'Your bookings, deposits and receipts, all in one place.',
        style: text.displaySmall?.copyWith(color: Colors.white),
      ),
      const SizedBox(height: Space.lg),
      Text(
        'See exactly what is held, what you will pay at the visit, and until when you can cancel for free.',
        style: text.bodyLarge?.copyWith(color: Palette.sageDeep),
      ),
    ]);
  }
}
