import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/i18n/i18n.dart';
import 'router.dart';
import 'theme.dart';

class RebooklyApp extends ConsumerWidget {
  const RebooklyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final strings = ref.watch(stringsProvider);
    return MaterialApp.router(
      title: 'Rebookly',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      themeMode: ThemeMode.light,
      routerConfig: ref.watch(routerProvider),
      // Material's own texts (date pickers, "OK", "Cancel") and right-to-left layout follow the chosen language.
      locale: Locale(strings.code),
      supportedLocales: [for (final language in appLanguages) Locale(language.code)],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      builder: (context, child) => StringsScope(strings: strings, child: child ?? const SizedBox.shrink()),
    );
  }
}
