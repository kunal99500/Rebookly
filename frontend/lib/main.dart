import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_web_plugins/url_strategy.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'app/app.dart';
import 'core/config.dart';
import 'core/format/time.dart';
import 'core/i18n/i18n.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  usePathUrlStrategy(); // clean addresses: /b/ravis-barbershop instead of /#/b/ravis-barbershop
  initTimeZones();
  if (AppConfig.authConfigured) {
    await Supabase.initialize(url: AppConfig.supabaseUrl, publishableKey: AppConfig.supabaseAnonKey);
  }
  if (AppConfig.firebaseConfigured) {
    await Firebase.initializeApp(
      options: const FirebaseOptions(
        apiKey: AppConfig.firebaseApiKey,
        authDomain: AppConfig.firebaseAuthDomain,
        projectId: AppConfig.firebaseProjectId,
        appId: AppConfig.firebaseAppId,
        messagingSenderId: AppConfig.firebaseMessagingSenderId,
      ),
    );
  }
  final strings = await Strings.load(await startingLanguage());
  runApp(ProviderScope(
    overrides: [stringsProvider.overrideWith((ref) => strings)],
    child: const RebooklyApp(),
  ));
}
