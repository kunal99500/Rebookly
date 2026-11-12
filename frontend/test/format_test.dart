import 'package:flutter_test/flutter_test.dart';
import 'package:rebookly_frontend/core/format/money.dart';
import 'package:rebookly_frontend/core/format/time.dart';

void main() {
  group('formatMoney shows amounts exactly as the backend sent them', () {
    test('Indian rupees use Indian grouping', () {
      expect(formatMoney('80.00', 'INR'), '₹80.00');
      expect(formatMoney('124560', 'INR'), '₹1,24,560.00');
    });

    test('other currencies', () {
      expect(formatMoney('45.5', 'USD'), r'$45.50');
      expect(formatMoney(12, 'GBP'), '£12.00');
    });

    test('whole amounts can drop the decimals for "from" prices', () {
      expect(formatMoney('300.00', 'INR', showZeroDecimals: false), '₹300');
      expect(formatMoney('299.50', 'INR', showZeroDecimals: false), '₹299.50');
    });

    test('missing or broken amounts show nothing rather than a wrong number', () {
      expect(formatMoney(null, 'INR'), '');
      expect(formatMoney('abc', 'INR'), '');
    });
  });

  group('times', () {
    setUpAll(initTimeZones);

    test('appointments are shown in the business time zone', () {
      final instant = DateTime.utc(2026, 11, 18, 11, 0);   // 11:00 UTC
      expect(formatTime(instant, 'Asia/Kolkata'), '4:30 PM');
      expect(formatTime(instant, 'Europe/London'), '11:00 AM');
    });

    test('an unknown time zone falls back to UTC instead of failing', () {
      expect(formatTime(DateTime.utc(2026, 11, 18, 9), 'Mars/Base'), '9:00 AM');
    });

    test('durations read naturally', () {
      expect(formatDuration(45), '45 min');
      expect(formatDuration(60), '1 hr');
      expect(formatDuration(90), '1 hr 30 min');
    });
  });
}
