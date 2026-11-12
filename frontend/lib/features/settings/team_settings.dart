import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/format/time.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import 'settings_common.dart';
import 'weekly_hours.dart';

typedef _Team = ({List<Period> hours, List<Map<String, dynamic>> staff, List<Map<String, dynamic>> services, List<Map<String, dynamic>> timeOff});

final _teamProvider = FutureProvider.autoDispose.family<_Team, String>((ref, id) async {
  final api = ref.watch(apiClientProvider);
  final base = '/api/owner/businesses/$id';
  final results = await Future.wait([
    api.get('$base/availability'),
    api.get('$base/team'),
    api.get('$base/services'),
    api.get('$base/time-off'),
  ]);
  return (hours: readHours(results[0]), staff: asList(results[1]), services: asList(results[2]), timeOff: asList(results[3]));
});

/// Opening hours, the team (who does what, and when), and time off.
class TeamSettingsScreen extends StatelessWidget {
  const TeamSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'Team and hours',
        subtitle: 'Clients only see times when someone who does that service is working.',
        builder: (context, id, business) => _TeamBody(businessId: id, timezone: '${business['timezone'] ?? 'UTC'}'),
      );
}

class _TeamBody extends ConsumerWidget {
  const _TeamBody({required this.businessId, required this.timezone});

  final String businessId;
  final String timezone;

  String get _base => '/api/owner/businesses/$businessId';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final api = ref.read(apiClientProvider);
    void reload() => ref.invalidate(_teamProvider(businessId));

    return AsyncView<_Team>(
      value: ref.watch(_teamProvider(businessId)),
      onRetry: reload,
      data: (team) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SectionHeader('Opening hours', subtitle: 'When the business is open. Each person can have their own hours below.'),
        WeeklyHoursEditor(
          initial: team.hours,
          onSave: (hours) async {
            if (await runSave(context, () => api.put('$_base/availability', body: {'hours': [for (final p in hours) p.toJson()]}))) reload();
          },
        ),
        const SizedBox(height: 48),
        SectionHeader(
          'Team',
          subtitle: 'Add everyone who takes bookings.',
          action: TextButton.icon(
            icon: const Icon(Icons.person_add_alt_1_outlined, size: 20),
            label: const Text('Add a person'),
            onPressed: () async {
              final name = await _askName(context, null);
              if (name == null || !context.mounted) return;
              if (await runSave(context, () => api.post('$_base/team', body: {'name': name}), done: '$name added.')) reload();
            },
          ),
        ),
        for (final person in team.staff)
          _Person(
            person: person,
            services: team.services,
            onChanged: reload,
            base: _base,
          ),
        const SizedBox(height: 48),
        SectionHeader(
          'Time off',
          subtitle: 'Holidays, sick days, or closing the whole business for a while.',
          action: TextButton.icon(
            icon: const Icon(Icons.beach_access_outlined, size: 20),
            label: const Text('Add time off'),
            onPressed: () async {
              final created = await showDialog<Map<String, dynamic>>(
                context: context,
                builder: (context) => _TimeOffDialog(staff: team.staff, timezone: timezone),
              );
              if (created == null || !context.mounted) return;
              try {
                final result = asMap(await api.post('$_base/time-off', body: created));
                reload();
                final affected = (result['affected_bookings'] as num?)?.toInt() ?? 0;
                if (context.mounted) {
                  showMessage(context, affected == 0
                      ? 'Time off added.'
                      : 'Time off added. $affected booking${affected == 1 ? '' : 's'} fall in it: move or cancel them in Bookings.');
                }
              } catch (error) {
                if (context.mounted) await runSave(context, () => Future.error(error));
              }
            },
          ),
        ),
        if (team.timeOff.isEmpty) Text('No time off planned.', style: text.bodyMedium?.copyWith(color: Palette.muted)),
        for (final off in team.timeOff)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.event_busy_outlined, color: Palette.waiting),
            title: Text(
              '${off['staff_name'] ?? _staffName(team.staff, off['staff_id']) ?? 'Whole business'}: '
              '${formatDayTime(DateTime.parse('${off['starts_at']}'), timezone)} to ${formatDayTime(DateTime.parse('${off['ends_at']}'), timezone)}',
              style: text.bodyMedium,
            ),
            subtitle: off['reason'] == null ? null : Text('${off['reason']}', style: text.bodySmall),
            trailing: IconButton(
              tooltip: 'Remove',
              icon: const Icon(Icons.delete_outline_rounded),
              onPressed: () async {
                if (await runSave(context, () => api.delete('$_base/time-off/${off['id']}'), done: 'Removed.')) reload();
              },
            ),
          ),
      ]),
    );
  }

  static String? _staffName(List<Map<String, dynamic>> staff, Object? id) =>
      id == null ? null : staff.where((p) => '${p['id']}' == '$id').map((p) => '${p['name']}').firstOrNull;
}

Future<String?> _askName(BuildContext context, String? current) {
  final controller = TextEditingController(text: current ?? '');
  return showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(current == null ? 'Add a person' : 'Rename'),
      content: TextField(controller: controller, autofocus: true, decoration: const InputDecoration(labelText: 'Name')),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.of(context).pop(controller.text.trim().isEmpty ? null : controller.text.trim()), child: const Text('Save')),
      ],
    ),
  );
}

class _Person extends ConsumerWidget {
  const _Person({required this.person, required this.services, required this.onChanged, required this.base});

  final Map<String, dynamic> person;
  final List<Map<String, dynamic>> services;
  final VoidCallback onChanged;
  final String base;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final api = ref.read(apiClientProvider);
    final active = person['is_active'] != false;
    final ids = [for (final id in (person['service_ids'] as List? ?? const [])) '$id'];
    final doing = ids.isEmpty ? 'Every service' : services.where((s) => ids.contains('${s['id']}')).map((s) => '${s['name']}').join(', ');
    final path = '$base/team/${person['id']}';

    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
      child: Panel(
        padding: const EdgeInsets.all(Space.lg),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            CircleAvatar(backgroundColor: Palette.sage, child: Text('${person['name']}'.characters.first.toUpperCase(), style: const TextStyle(color: Palette.forest))),
            const SizedBox(width: Space.md),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${person['name']}${active ? '' : ' (not taking bookings)'}', style: text.titleMedium),
                Text(doing, style: text.bodySmall, maxLines: 2, overflow: TextOverflow.ellipsis),
              ]),
            ),
            PopupMenuButton<String>(
              onSelected: (action) async {
                switch (action) {
                  case 'rename':
                    final name = await _askName(context, '${person['name']}');
                    if (name != null && context.mounted && await runSave(context, () => api.patch(path, body: {'name': name}))) onChanged();
                  case 'services':
                    final chosen = await showDialog<List<String>>(
                      context: context,
                      builder: (context) => _ServicesDialog(services: services, selected: ids),
                    );
                    if (chosen != null && context.mounted && await runSave(context, () => api.patch(path, body: {'service_ids': chosen}))) onChanged();
                  case 'hours':
                    await showDialog<void>(
                      context: context,
                      builder: (context) => AlertDialog(
                        title: Text('${person['name']}’s hours'),
                        content: SizedBox(
                          width: 640,
                          child: SingleChildScrollView(
                            child: WeeklyHoursEditor(
                              initial: readHours(person['hours'] ?? const []),
                              onSave: (hours) async {
                                if (await runSave(context, () => api.put('$path/hours', body: {'hours': [for (final p in hours) p.toJson()]}))) {
                                  onChanged();
                                  if (context.mounted) Navigator.of(context).pop();
                                }
                              },
                            ),
                          ),
                        ),
                      ),
                    );
                  case 'toggle':
                    if (await runSave(context, () => api.patch(path, body: {'is_active': !active}))) onChanged();
                }
              },
              itemBuilder: (context) => [
                const PopupMenuItem(value: 'rename', child: Text('Rename')),
                const PopupMenuItem(value: 'services', child: Text('Services they do')),
                const PopupMenuItem(value: 'hours', child: Text('Their working hours')),
                PopupMenuItem(value: 'toggle', child: Text(active ? 'Stop taking bookings' : 'Start taking bookings')),
              ],
            ),
          ]),
        ]),
      ),
    );
  }
}

class _ServicesDialog extends StatefulWidget {
  const _ServicesDialog({required this.services, required this.selected});

  final List<Map<String, dynamic>> services;
  final List<String> selected;

  @override
  State<_ServicesDialog> createState() => _ServicesDialogState();
}

class _ServicesDialogState extends State<_ServicesDialog> {
  late final Set<String> _chosen = {...widget.selected};

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Services they do'),
        content: SizedBox(
          width: 420,
          child: ListView(shrinkWrap: true, children: [
            for (final service in widget.services)
              CheckboxListTile(
                value: _chosen.contains('${service['id']}'),
                title: Text('${service['name']}'),
                onChanged: (on) => setState(() => on == true ? _chosen.add('${service['id']}') : _chosen.remove('${service['id']}')),
              ),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(context).pop(_chosen.toList()), child: const Text('Save')),
        ],
      );
}

class _TimeOffDialog extends StatefulWidget {
  const _TimeOffDialog({required this.staff, required this.timezone});

  final List<Map<String, dynamic>> staff;
  final String timezone;

  @override
  State<_TimeOffDialog> createState() => _TimeOffDialogState();
}

class _TimeOffDialogState extends State<_TimeOffDialog> {
  String? _staffId;
  DateTimeRange? _days;
  final _reason = TextEditingController();

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  /// Whole days in the business's time zone, sent with the correct offset (e.g. +05:30).
  String _boundary(DateTime day) {
    final local = inZone(DateTime.now(), widget.timezone);
    final offset = local.timeZoneOffset;
    final sign = offset.isNegative ? '-' : '+';
    final hours = offset.inHours.abs().toString().padLeft(2, '0');
    final minutes = (offset.inMinutes.abs() % 60).toString().padLeft(2, '0');
    return '${DateFormat('yyyy-MM-dd').format(day)}T00:00:00$sign$hours:$minutes';
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final label = _days == null
        ? 'Choose the days'
        : '${DateFormat('d MMM').format(_days!.start)} to ${DateFormat('d MMM yyyy').format(_days!.end)}';
    return AlertDialog(
      title: const Text('Add time off'),
      content: SizedBox(
        width: 420,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          DropdownMenu<String?>(
            initialSelection: null,
            label: const Text('Who'),
            width: 400,
            dropdownMenuEntries: [
              const DropdownMenuEntry(value: null, label: 'The whole business'),
              for (final person in widget.staff) DropdownMenuEntry(value: '${person['id']}', label: '${person['name']}'),
            ],
            onSelected: (value) => setState(() => _staffId = value),
          ),
          const SizedBox(height: Space.md),
          OutlinedButton.icon(
            icon: const Icon(Icons.date_range_rounded, size: 20),
            label: Text(label),
            onPressed: () async {
              final now = DateTime.now();
              final picked = await showDateRangePicker(context: context, firstDate: now, lastDate: now.add(const Duration(days: 365)));
              if (picked != null) setState(() => _days = picked);
            },
          ),
          const SizedBox(height: Space.md),
          TextField(controller: _reason, maxLength: 120, decoration: const InputDecoration(labelText: 'Reason (only you see it)')),
          Text('Whole days. Bookings already in this time stay; you’ll see how many to move.', style: text.bodySmall),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(
          onPressed: _days == null
              ? null
              : () => Navigator.of(context).pop({
                    if (_staffId != null) 'staff_id': _staffId,
                    'starts_at': _boundary(_days!.start),
                    'ends_at': _boundary(_days!.end.add(const Duration(days: 1))),
                    if (_reason.text.trim().isNotEmpty) 'reason': _reason.text.trim(),
                  }),
          child: const Text('Add'),
        ),
      ],
    );
  }
}
