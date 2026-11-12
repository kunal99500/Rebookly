import 'package:flutter/material.dart';

import '../../app/tokens.dart';
import '../../shared/layout.dart';
import 'settings_common.dart';

const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

/// One opening period on one day, in local time ("09:00").
class Period {
  Period(this.weekday, this.start, this.end);
  final int weekday;
  String start;
  String end;

  Map<String, dynamic> toJson() => {'weekday': weekday, 'start': start, 'end': end};
}

List<Period> readHours(Object? json) {
  final list = json is Map ? (json['hours'] as List? ?? const []) : (json as List? ?? const []);
  return [for (final item in list.cast<Map>()) Period((item['weekday'] as num).toInt(), clock(item['start']), clock(item['end']))];
}

/// Seven days, each open or closed, with one or more periods (e.g. 10:00–14:00 and 15:00–20:00).
class WeeklyHoursEditor extends StatefulWidget {
  const WeeklyHoursEditor({super.key, required this.initial, required this.onSave, this.saveLabel = 'Save hours'});

  final List<Period> initial;
  final Future<void> Function(List<Period> hours) onSave;
  final String saveLabel;

  @override
  State<WeeklyHoursEditor> createState() => _WeeklyHoursEditorState();
}

class _WeeklyHoursEditorState extends State<WeeklyHoursEditor> {
  late final List<Period> _hours = [for (final p in widget.initial) Period(p.weekday, p.start, p.end)];

  Future<String?> _pick(String current) async {
    final parts = current.split(':');
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: int.tryParse(parts.first) ?? 9, minute: parts.length > 1 ? int.tryParse(parts[1]) ?? 0 : 0),
    );
    if (picked == null) return null;
    return '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}';
  }

  String _label(String value) {
    final parts = value.split(':');
    final hour = int.tryParse(parts.first) ?? 0;
    final minute = parts.length > 1 ? parts[1] : '00';
    final twelve = hour % 12 == 0 ? 12 : hour % 12;
    return '$twelve:$minute ${hour < 12 ? 'AM' : 'PM'}';
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Panel(
        padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.sm),
        child: Column(children: [
          for (var day = 0; day < 7; day++) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: Space.sm),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SizedBox(
                  width: 128,
                  child: Row(children: [
                    Switch(
                      value: _hours.any((p) => p.weekday == day),
                      onChanged: (open) => setState(() {
                        if (open) {
                          _hours.add(Period(day, '10:00', '19:00'));
                        } else {
                          _hours.removeWhere((p) => p.weekday == day);
                        }
                      }),
                    ),
                    const SizedBox(width: 6),
                    Text(weekdays[day].substring(0, 3), style: text.titleSmall),
                  ]),
                ),
                Expanded(
                  child: _hours.every((p) => p.weekday != day)
                      ? Padding(padding: const EdgeInsets.only(top: 12), child: Text('Closed', style: text.bodyMedium?.copyWith(color: Palette.muted)))
                      : Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
                          for (final period in _hours.where((p) => p.weekday == day))
                            InputChip(
                              label: Text('${_label(period.start)} to ${_label(period.end)}'),
                              onPressed: () async {
                                final start = await _pick(period.start);
                                if (start == null || !mounted) return;
                                final end = await _pick(period.end);
                                if (end == null) return;
                                setState(() {
                                  period.start = start;
                                  period.end = end;
                                });
                              },
                              onDeleted: () => setState(() => _hours.remove(period)),
                            ),
                          ActionChip(
                            avatar: const Icon(Icons.add_rounded, size: 18),
                            label: const Text('Add a break'),
                            tooltip: 'Add another opening period this day',
                            onPressed: () => setState(() => _hours.add(Period(day, '15:00', '19:00'))),
                          ),
                        ]),
                ),
              ]),
            ),
            if (day < 6) const Divider(),
          ],
        ]),
      ),
      const SizedBox(height: Space.sm),
      Text('Tap a time to change it. Use “Add a break” for split days, like 10 to 2 and 3 to 8.', style: text.bodySmall),
      const SizedBox(height: Space.lg),
      BusyButton(label: widget.saveLabel, onPressed: () => widget.onSave(_hours)),
    ]);
  }
}
