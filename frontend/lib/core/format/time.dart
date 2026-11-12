import 'package:intl/intl.dart';
import 'package:timezone/data/latest_10y.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

/// Appointment times are always shown in the BUSINESS's time zone (where the visit happens),
/// whatever the viewer's device is set to.
void initTimeZones() => tz_data.initializeTimeZones();

tz.Location _location(String name) {
  try {
    return tz.getLocation(name);
  } catch (_) {
    return tz.UTC;
  }
}

tz.TZDateTime inZone(DateTime instant, String timezone) => tz.TZDateTime.from(instant, _location(timezone));

/// "Tue 18 Nov, 4:30 PM"
String formatDayTime(DateTime instant, String timezone) =>
    DateFormat('EEE d MMM, h:mm a').format(inZone(instant, timezone));

/// "4:30 PM"
String formatTime(DateTime instant, String timezone) => DateFormat('h:mm a').format(inZone(instant, timezone));

/// "Tuesday 18 November"
String formatDay(DateTime instant, String timezone) => DateFormat('EEEE d MMMM').format(inZone(instant, timezone));

/// "45 min", "1 hr", "1 hr 30 min"
String formatDuration(int minutes) {
  if (minutes < 60) return '$minutes min';
  final hours = minutes ~/ 60;
  final rest = minutes % 60;
  return rest == 0 ? '$hours hr' : '$hours hr $rest min';
}

/// "Tue" (for a date that is already in the business's time zone)
String formatDayShort(DateTime local) => DateFormat('EEE').format(local);

/// "2026-11-18": the form the backend uses for dates.
String isoDate(DateTime local) => DateFormat('yyyy-MM-dd').format(local);

/// Midnight at the start of [day] (a calendar date) in [timezone], as a UTC instant in ISO form.
String localMidnightUtc(DateTime day, String timezone) =>
    tz.TZDateTime(_location(timezone), day.year, day.month, day.day).toUtc().toIso8601String();
