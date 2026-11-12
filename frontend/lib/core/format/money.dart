import 'package:intl/intl.dart';

/// Shows an amount exactly as the backend calculated it. The app never does money arithmetic:
/// prices, deposits, fees and taxes are always worked out by the server.
///
/// [amount] can be the backend's decimal string ("80.00") or a number.
String formatMoney(Object? amount, String currency, {bool showZeroDecimals = true}) {
  final value = amount is num ? amount : num.tryParse(amount?.toString() ?? '');
  if (value == null) return '';
  final code = currency.toUpperCase();
  final symbol = NumberFormat.simpleCurrency(name: code).currencySymbol;
  final digits = !showZeroDecimals && value == value.roundToDouble() ? 0 : 2;
  return NumberFormat.currency(locale: _localeFor(code), name: code, symbol: symbol, decimalDigits: digits)
      .format(value);
}

/// Indian rupees group as 1,24,560.00; most other currencies as 124,560.00.
String _localeFor(String currency) => switch (currency) {
      'INR' => 'en_IN',
      'GBP' => 'en_GB',
      'EUR' => 'en_IE',
      'AUD' => 'en_AU',
      'CAD' => 'en_CA',
      _ => 'en_US',
    };

/// Adds the currency to plain amounts inside a backend sentence: "Fee: 37.50" -> "Fee: ₹37.50".
String withCurrency(String sentence, String currency) => sentence.replaceAllMapped(
      RegExp(r'(?<![\d.,₹$£€])(\d+(?:\.\d{1,2}))'),
      (match) => formatMoney(match.group(1), currency),
    );
