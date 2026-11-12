import 'package:flutter/material.dart';

import 'tokens.dart';

/// Type scale (roughly a 1.25 ratio), with Bricolage for display moments and Figtree for reading.
TextTheme _textTheme() {
  const display = Fonts.display;
  const body = Fonts.body;
  return const TextTheme(
    displayLarge: TextStyle(fontFamily: display, fontSize: 64, height: 1.0, fontWeight: FontWeight.w800, letterSpacing: -2.0, color: Palette.ink),
    displayMedium: TextStyle(fontFamily: display, fontSize: 48, height: 1.04, fontWeight: FontWeight.w800, letterSpacing: -1.4, color: Palette.ink),
    displaySmall: TextStyle(fontFamily: display, fontSize: 36, height: 1.08, fontWeight: FontWeight.w800, letterSpacing: -0.9, color: Palette.ink),
    headlineMedium: TextStyle(fontFamily: display, fontSize: 28, height: 1.15, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: Palette.ink),
    headlineSmall: TextStyle(fontFamily: display, fontSize: 22, height: 1.2, fontWeight: FontWeight.w700, letterSpacing: -0.3, color: Palette.ink),
    titleLarge: TextStyle(fontFamily: body, fontSize: 18, height: 1.3, fontWeight: FontWeight.w700, color: Palette.ink),
    titleMedium: TextStyle(fontFamily: body, fontSize: 16, height: 1.35, fontWeight: FontWeight.w600, color: Palette.ink),
    titleSmall: TextStyle(fontFamily: body, fontSize: 14, height: 1.35, fontWeight: FontWeight.w600, color: Palette.ink),
    bodyLarge: TextStyle(fontFamily: body, fontSize: 16, height: 1.55, fontWeight: FontWeight.w400, color: Palette.ink),
    bodyMedium: TextStyle(fontFamily: body, fontSize: 14, height: 1.5, fontWeight: FontWeight.w400, color: Palette.ink),
    bodySmall: TextStyle(fontFamily: body, fontSize: 13, height: 1.45, fontWeight: FontWeight.w400, color: Palette.muted),
    labelLarge: TextStyle(fontFamily: body, fontSize: 15, height: 1.2, fontWeight: FontWeight.w600, letterSpacing: 0.1),
    labelMedium: TextStyle(fontFamily: body, fontSize: 13, height: 1.2, fontWeight: FontWeight.w600),
    labelSmall: TextStyle(fontFamily: body, fontSize: 12, height: 1.2, fontWeight: FontWeight.w600),
  );
}

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: Palette.forest, brightness: Brightness.light).copyWith(
    primary: Palette.forest,
    onPrimary: Colors.white,
    secondary: Palette.forestDeep,
    surface: Palette.surface,
    onSurface: Palette.ink,
    onSurfaceVariant: Palette.muted,
    outline: Palette.line,
    outlineVariant: Palette.line,
    error: Palette.problem,
    surfaceContainerHighest: Palette.sage,
  );
  final text = _textTheme();
  final controlShape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.control));

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: Fonts.body,
    textTheme: text,
    scaffoldBackgroundColor: Palette.paper,
    splashFactory: InkRipple.splashFactory,
    visualDensity: VisualDensity.standard,
    appBarTheme: AppBarTheme(
      backgroundColor: Palette.paper,
      surfaceTintColor: Colors.transparent,
      foregroundColor: Palette.ink,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: text.titleLarge,
    ),
    dividerTheme: const DividerThemeData(color: Palette.line, thickness: 1, space: 1),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: Palette.forest,
        foregroundColor: Colors.white,
        disabledBackgroundColor: Palette.sageDeep,
        disabledForegroundColor: Palette.muted,
        minimumSize: const Size(0, 52),
        padding: const EdgeInsets.symmetric(horizontal: 22),
        shape: controlShape,
        textStyle: text.labelLarge,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: Palette.ink,
        minimumSize: const Size(0, 52),
        padding: const EdgeInsets.symmetric(horizontal: 20),
        side: const BorderSide(color: Palette.line, width: 1.2),
        shape: controlShape,
        textStyle: text.labelLarge,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: Palette.forest,
        minimumSize: const Size(0, 44),
        padding: const EdgeInsets.symmetric(horizontal: 12),
        shape: controlShape,
        textStyle: text.labelLarge,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Palette.surface,
      hintStyle: text.bodyLarge?.copyWith(color: Palette.faint),
      labelStyle: text.bodyMedium?.copyWith(color: Palette.muted),
      floatingLabelStyle: text.bodyMedium?.copyWith(color: Palette.forest, fontWeight: FontWeight.w600),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: _inputBorder(Palette.line),
      enabledBorder: _inputBorder(Palette.line),
      focusedBorder: _inputBorder(Palette.forest, width: 1.6),
      errorBorder: _inputBorder(Palette.problem),
      focusedErrorBorder: _inputBorder(Palette.problem, width: 1.6),
      errorStyle: text.bodySmall?.copyWith(color: Palette.problem),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: Palette.surface,
      selectedColor: Palette.sage,
      secondarySelectedColor: Palette.sage,
      side: const BorderSide(color: Palette.line),
      shape: const StadiumBorder(),
      labelStyle: text.labelMedium?.copyWith(color: Palette.ink),
      secondaryLabelStyle: text.labelMedium?.copyWith(color: Palette.forest),
      checkmarkColor: Palette.forest,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Palette.surface,
      surfaceTintColor: Colors.transparent,
      indicatorColor: Palette.sage,
      height: 68,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => text.labelSmall?.copyWith(
          color: states.contains(WidgetState.selected) ? Palette.forest : Palette.muted,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(color: states.contains(WidgetState.selected) ? Palette.forest : Palette.muted),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: Palette.ink,
      contentTextStyle: text.bodyMedium?.copyWith(color: Colors.white),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.control)),
      insetPadding: const EdgeInsets.all(Space.lg),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(color: Palette.forest),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(color: Palette.ink, borderRadius: BorderRadius.circular(8)),
      textStyle: text.labelSmall?.copyWith(color: Colors.white),
    ),
  );
}

OutlineInputBorder _inputBorder(Color color, {double width = 1.2}) => OutlineInputBorder(
      borderRadius: BorderRadius.circular(Radii.control),
      borderSide: BorderSide(color: color, width: width),
    );
