import 'dart:convert';
import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// A language the app's screens can be shown in.
class AppLanguage {
  const AppLanguage(this.code, this.nativeName, this.englishName, {this.rtl = false});

  final String code;
  final String nativeName;
  final String englishName;
  final bool rtl;   // written right to left (Arabic, Urdu)
}

const appLanguages = [
  AppLanguage('en', 'English', 'English'),
  AppLanguage('hi', 'हिन्दी', 'Hindi'),
  AppLanguage('bn', 'বাংলা', 'Bengali'),
  AppLanguage('mr', 'मराठी', 'Marathi'),
  AppLanguage('ta', 'தமிழ்', 'Tamil'),
  AppLanguage('te', 'తెలుగు', 'Telugu'),
  AppLanguage('kn', 'ಕನ್ನಡ', 'Kannada'),
  AppLanguage('ml', 'മലയാളം', 'Malayalam'),
  AppLanguage('gu', 'ગુજરાતી', 'Gujarati'),
  AppLanguage('pa', 'ਪੰਜਾਬੀ', 'Punjabi'),
  AppLanguage('ur', 'اردو', 'Urdu', rtl: true),
  AppLanguage('es', 'Español', 'Spanish'),
  AppLanguage('pt', 'Português', 'Portuguese'),
  AppLanguage('fr', 'Français', 'French'),
  AppLanguage('ar', 'العربية', 'Arabic', rtl: true),
  AppLanguage('id', 'Bahasa Indonesia', 'Indonesian'),
];

/// The app's sentences in one language, with English as the fallback for anything not translated yet.
class Strings {
  const Strings(this.code, this._own, this._english);

  final String code;
  final Map<String, String> _own;
  final Map<String, String> _english;

  static const empty = Strings('en', {}, {});

  /// [key] looks like "home.title"; {placeholders} are filled from [params].
  String t(String key, [Map<String, Object?>? params]) {
    var text = _own[key] ?? _english[key] ?? key;
    params?.forEach((name, value) => text = text.replaceAll('{$name}', '$value'));
    return text;
  }

  static Future<Map<String, String>> _load(String code) async {
    try {
      final raw = jsonDecode(await rootBundle.loadString('assets/i18n/$code.json')) as Map<String, dynamic>;
      return {for (final e in raw.entries) if (!e.key.startsWith('_')) e.key: '${e.value}'};
    } catch (_) {
      return const {};
    }
  }

  static Future<Strings> load(String code) async {
    final english = await _load('en');
    return Strings(code, code == 'en' ? english : await _load(code), english);
  }
}

const _savedKey = 'rebookly.language';

/// The language chosen last time, or the device's language if the app has it, or English.
Future<String> startingLanguage() async {
  try {
    final saved = (await SharedPreferences.getInstance()).getString(_savedKey);
    if (saved != null && appLanguages.any((l) => l.code == saved)) return saved;
  } catch (_) {}
  final device = PlatformDispatcher.instance.locale.languageCode;
  return appLanguages.any((l) => l.code == device) ? device : 'en';
}

final stringsProvider = StateProvider<Strings>((ref) => Strings.empty);

Future<void> changeLanguage(WidgetRef ref, String code) async {
  ref.read(stringsProvider.notifier).state = await Strings.load(code);
  try {
    await (await SharedPreferences.getInstance()).setString(_savedKey, code);
  } catch (_) {}
}

/// Makes the current sentences available below it; every screen reads them with context.tr(...).
class StringsScope extends InheritedWidget {
  const StringsScope({super.key, required this.strings, required super.child});

  final Strings strings;

  static Strings of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<StringsScope>()?.strings ?? Strings.empty;

  @override
  bool updateShouldNotify(StringsScope oldWidget) => oldWidget.strings != strings;
}

extension Translate on BuildContext {
  String tr(String key, [Map<String, Object?>? params]) => StringsScope.of(this).t(key, params);
}
