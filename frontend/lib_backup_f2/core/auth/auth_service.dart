import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../config.dart';

/// A sign-in problem in plain words.
class AuthFailure implements Exception {
  const AuthFailure(this.message);
  final String message;

  @override
  String toString() => message;
}

/// Sign-in through Supabase: phone codes for clients, email and password for business owners.
///
/// It's a [ChangeNotifier] so the router can react the moment someone signs in or out.
class AuthService extends ChangeNotifier {
  AuthService() {
    if (isConfigured) {
      _subscription = _auth.onAuthStateChange.listen((_) => notifyListeners());
    }
  }

  StreamSubscription<AuthState>? _subscription;

  bool get isConfigured => AppConfig.authConfigured;
  GoTrueClient get _auth => Supabase.instance.client.auth;

  Session? get session => isConfigured ? _auth.currentSession : null;
  bool get isSignedIn => session != null;
  String? get email => session?.user.email;
  String? get phone => session?.user.phone;

  /// Clients: send a 6-digit code by SMS. [phone] must be in international form, e.g. +919876543210.
  Future<void> sendPhoneCode(String phone) => _guard(() => _auth.signInWithOtp(phone: phone));

  Future<void> verifyPhoneCode(String phone, String code) =>
      _guard(() => _auth.verifyOTP(type: OtpType.sms, phone: phone, token: code));

  /// Business owners.
  Future<void> signInWithEmail(String email, String password) =>
      _guard(() => _auth.signInWithPassword(email: email, password: password));

  /// Returns true when the owner is signed in straight away, false when they must confirm their email first.
  Future<bool> createOwnerAccount(String email, String password) async {
    final response = await _guard(() => _auth.signUp(email: email, password: password));
    return response.session != null;
  }

  Future<void> signOut() => _guard(() => _auth.signOut());

  Future<T> _guard<T>(Future<T> Function() action) async {
    if (!isConfigured) {
      throw const AuthFailure("Sign-in isn't set up in this build. Add SUPABASE_URL and SUPABASE_ANON_KEY.");
    }
    try {
      return await action();
    } on AuthException catch (error) {
      throw AuthFailure(_readable(error.message));
    }
  }

  static String _readable(String message) {
    final text = message.toLowerCase();
    if (text.contains('invalid login')) return "That email and password don't match.";
    if (text.contains('expired') || (text.contains('invalid') && text.contains('token'))) {
      return 'That code is wrong or has expired. Ask for a new one.';
    }
    if (text.contains('rate limit') || text.contains('too many')) {
      return 'Too many attempts. Wait a minute, then try again.';
    }
    if (text.contains('already registered')) return 'An account with this email already exists. Sign in instead.';
    if (text.contains('password')) return message;
    return message.isEmpty ? 'Sign-in failed. Try again.' : message;
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }
}

final authServiceProvider = ChangeNotifierProvider<AuthService>((ref) => AuthService());
