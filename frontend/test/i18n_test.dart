import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:rebookly_frontend/core/i18n/i18n.dart';

void main() {
  test('a translated sentence fills its placeholders, and falls back to English', () {
    const strings = Strings('hi', {'signin.sent': 'हमने {phone} पर कोड भेजा है'}, {'signin.sent': 'We sent a code to {phone}', 'only.english': 'Hello'});
    expect(strings.t('signin.sent', {'phone': '+91 97200'}), 'हमने +91 97200 पर कोड भेजा है');
    expect(strings.t('only.english'), 'Hello');
    expect(strings.t('missing.key'), 'missing.key');
  });

  test('every language file has the same placeholders as English', () {
    final folder = Directory('assets/i18n');
    final english = jsonDecode(File('${folder.path}/en.json').readAsStringSync()) as Map<String, dynamic>;
    final pattern = RegExp(r'\{\w+\}');
    for (final file in folder.listSync().whereType<File>().where((f) => f.path.endsWith('.json'))) {
      final other = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
      for (final entry in other.entries.where((e) => !e.key.startsWith('_'))) {
        expect(english.containsKey(entry.key), isTrue, reason: '${file.path}: unknown key ${entry.key}');
        final want = pattern.allMatches('${english[entry.key]}').map((m) => m[0]).toSet();
        final got = pattern.allMatches('${entry.value}').map((m) => m[0]).toSet();
        expect(got, want, reason: '${file.path}: ${entry.key}');
      }
    }
  });

  test('every language the app offers is right-to-left only when it should be', () {
    expect(appLanguages.where((l) => l.rtl).map((l) => l.code).toSet(), {'ur', 'ar'});
  });
}
