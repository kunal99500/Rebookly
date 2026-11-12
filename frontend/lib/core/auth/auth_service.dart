import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart' as fb;
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

/// Who is signed in.
///   * Clients: Firebase, with a code sent to their phone.
///   * Business owners: Supabase, with email and password.
/// One person can be both at once. It's a [ChangeNotifier] so the router reacts to sign-in and sign-out.
class AuthService extends ChangeNotifier {
  AuthService() {
    if (AppConfig.authConfigured) {
      _supabaseSub = Supabase.instance.client.auth.onAuthStateChange.listen((_) => notifyListeners());
    }
    if (AppConfig.firebaseConfigured) {
      _firebaseSub = fb.FirebaseAuth.instance.authStateChanges().listen((_) => notifyListeners());
    }
  }

  StreamSubscription<AuthState>? _supabaseSub;
  StreamSubscription<fb.User?>? _firebaseSub;
  fb.ConfirmationResult? _pendingCode;

  // ---------- clients (Firebase phone codes) ----------

  fb.User? get client => AppConfig.firebaseConfigured ? fb.FirebaseAuth.instance.currentUser : null;
  bool get isClientSignedIn => client != null;
  String? get clientPhone => client?.phoneNumber;

  /// Send a 6-digit code by SMS. [phone] in international form, e.g. +919876543210.
  /// On the web Firebase shows an invisible "I'm not a robot" check first, which usually passes silently.
  Future<void> sendPhoneCode(String phone) async {
    if (!AppConfig.firebaseConfigured) {
      throw const AuthFailure("Phone sign-in isn't set up in this build. Add the Firebase settings.");
    }
    try {
      _pendingCode = await fb.FirebaseAuth.instance.signInWithPhoneNumber(phone);
    } on fb.FirebaseAuthException catch (error) {
      throw AuthFailure(_firebaseMessage(error));
    }
  }

  Future<void> verifyPhoneCode(String code) async {
    final pending = _pendingCode;
    if (pending == null) throw const AuthFailure('Ask for a code first.');
    try {
      await pending.confirm(code);
      _pendingCode = null;
    } on fb.FirebaseAuthException catch (error) {
      throw AuthFailure(_firebaseMessage(error));
    }
  }

  Future<String?> clientToken() async => client?.getIdToken();

  // ---------- business owners (Supabase email) ----------

  Session? get ownerSession => AppConfig.authConfigured ? Supabase.instance.client.auth.currentSession : null;
  bool get isOwnerSignedIn => ownerSession != null;
  String? get email => ownerSession?.user.email;
  String? ownerToken() => ownerSession?.accessToken;

  Future<void> signInWithEmail(String email, String password) =>
      _supabase(() => Supabase.instance.client.auth.signInWithPassword(email: email, password: password));

  /// True when the owner is signed in straight away; false when they must confirm their email first.
  Future<bool> createOwnerAccount(String email, String password) async {
    final response = await _supabase(() => Supabase.instance.client.auth.signUp(email: email, password: password));
    return response.session != null;
  }

  // ---------- both ----------

  Future<void> signOutClient() async {
    if (AppConfig.firebaseConfigured) await fb.FirebaseAuth.instance.signOut();
  }

  Future<void> signOutOwner() => _supabase(() => Supabase.instance.client.auth.signOut());

  Future<T> _supabase<T>(Future<T> Function() action) async {
    if (!AppConfig.authConfigured) {
      throw const AuthFailure("Business sign-in isn't set up in this build. Add the Supabase settings.");
    }
    try {
      return await action();
    } on AuthException catch (error) {
      throw AuthFailure(_supabaseMessage(error.message));
    }
  }

  static String _firebaseMessage(fb.FirebaseAuthException error) => switch (error.code) {
        'invalid-phone-number' => 'That phone number doesn’t look right. Include the country code.',
        'invalid-verification-code' => 'That code isn’t right. Check it and try again.',
        'code-expired' || 'session-expired' => 'That code has expired. Ask for a new one.',
        'too-many-requests' => 'Too many attempts. Wait a few minutes, then try again.',
        'quota-exceeded' => 'We can’t send more codes right now. Try again later.',
        'captcha-check-failed' => 'The robot check didn’t pass. Reload the page and try again.',
        'operation-not-allowed' => 'Phone sign-in is switched off for this app.',
        _ => error.message ?? 'Sign-in failed. Try again.',
      };

  static String _supabaseMessage(String message) {
    final text = message.toLowerCase();
    if (text.contains('invalid login')) return "That email and password don't match.";
    if (text.contains('rate limit') || text.contains('too many')) return 'Too many attempts. Wait a minute, then try again.';
    if (text.contains('already registered')) return 'An account with this email already exists. Sign in instead.';
    if (text.contains('email not confirmed')) return 'Confirm your email first: open the link we sent you.';
    return message.isEmpty ? 'Sign-in failed. Try again.' : message;
  }

  @override
  void dispose() {
    _supabaseSub?.cancel();
    _firebaseSub?.cancel();
    super.dispose();
  }
}

final authServiceProvider = ChangeNotifierProvider<AuthService>((ref) => AuthService());
