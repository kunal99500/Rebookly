import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_web_plugins/url_strategy.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'app/app.dart';
import 'core/config.dart';
import 'core/format/time.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  usePathUrlStrategy(); // clean addresses: /b/ravis-barbershop instead of /#/b/ravis-barbershop
  initTimeZones();
  // Shows in the PowerShell window at start-up, so we can see whether the settings arrived.
  debugPrint('Rebookly config: API=${AppConfig.apiBaseUrl}, '
      'Supabase URL set=${AppConfig.supabaseUrl.isNotEmpty}, key set=${AppConfig.supabaseAnonKey.isNotEmpty}');
  if (AppConfig.authConfigured) {
    await Supabase.initialize(url: AppConfig.supabaseUrl, publishableKey: AppConfig.supabaseAnonKey);
  }
  runApp(const ProviderScope(child: RebooklyApp()));
}
