import 'package:flutter/material.dart';

/// Rebookly's design tokens. Every colour, size and radius in the app comes from here.
abstract final class Palette {
  static const ink = Color(0xFF15201C);       // text and strong marks
  static const forest = Color(0xFF1F4D3F);    // the brand: actions, focus, links
  static const forestDeep = Color(0xFF15382D); // pressed states, the owner sidebar accent
  static const paper = Color(0xFFFAFAF7);     // page background
  static const surface = Color(0xFFFFFFFF);   // raised things: tickets, sheets, inputs
  static const sage = Color(0xFFE4EEE8);      // quiet panels, selected states
  static const sageDeep = Color(0xFFCFE0D6);
  static const line = Color(0xFFE2E6E1);      // borders and dividers
  static const muted = Color(0xFF5B665F);     // secondary text (AA contrast on paper)
  static const faint = Color(0xFF8A938D);     // hints and placeholders

  // Money states: the same colour always means the same thing about money.
  static const held = Color(0xFF2E62A0);
  static const heldBg = Color(0xFFE9F0FA);
  static const waiting = Color(0xFF9A5F0B);
  static const waitingBg = Color(0xFFFCF1DC);
  static const released = Color(0xFF1F7A4D);
  static const releasedBg = Color(0xFFE3F3EA);
  static const problem = Color(0xFFB23B3B);
  static const problemBg = Color(0xFFFBE9E9);
  static const charged = ink;
  static const chargedBg = Color(0xFFEDEFEC);
}

abstract final class Space {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 24.0;
  static const xxl = 32.0;
  static const section = 56.0;
}

/// Radii carry hierarchy: small things are tighter, big surfaces softer.
abstract final class Radii {
  static const chip = 999.0;
  static const control = 12.0;
  static const card = 16.0;
  static const sheet = 24.0;
}

abstract final class Breakpoints {
  static const wide = 900.0;     // two-column layouts, top navigation instead of the bottom bar
  static const owner = 1024.0;   // owner sidebar
  static const readable = 720.0; // comfortable reading width
  static const page = 1120.0;
}

abstract final class Fonts {
  static const display = 'Bricolage';
  static const body = 'Figtree';
  static const tabular = [FontFeature.tabularFigures()];
}
