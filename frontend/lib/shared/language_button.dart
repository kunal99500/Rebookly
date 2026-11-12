import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/tokens.dart';
import '../core/i18n/i18n.dart';

/// A globe button that lets anyone switch the app's language. The choice is remembered on this device.
class LanguageButton extends ConsumerWidget {
  const LanguageButton({super.key, this.onDark = false});

  final bool onDark;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = ref.watch(stringsProvider).code;
    return IconButton(
      tooltip: context.tr('language.choose'),
      icon: Icon(Icons.translate_rounded, color: onDark ? Colors.white : Palette.ink),
      onPressed: () async {
        final chosen = await showDialog<String>(
          context: context,
          builder: (context) => SimpleDialog(
            title: Text(context.tr('language.choose')),
            children: [
              for (final language in appLanguages)
                SimpleDialogOption(
                  onPressed: () => Navigator.of(context).pop(language.code),
                  child: Row(children: [
                    Expanded(child: Text(language.nativeName, style: Theme.of(context).textTheme.titleMedium)),
                    if (language.code != 'en') Text(language.englishName, style: Theme.of(context).textTheme.bodySmall),
                    if (language.code == current) ...[
                      const SizedBox(width: Space.sm),
                      const Icon(Icons.check_rounded, color: Palette.forest, size: 20),
                    ],
                  ]),
                ),
            ],
          ),
        );
        if (chosen != null) await changeLanguage(ref, chosen);
      },
    );
  }
}
