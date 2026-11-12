import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/format/time.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import '../settings/settings_common.dart';
import 'day_data.dart';
import 'owner_page.dart';

/// Group class sessions: seats taken, open new sessions from your hours, block a session.
class ClassesScreen extends StatelessWidget {
  const ClassesScreen({super.key});

  @override
  Widget build(BuildContext context) => OwnerPage(
        title: 'Classes',
        builder: (context, id, business) => _Classes(businessId: id, timezone: '${business['timezone'] ?? 'UTC'}'),
      );
}

class _Classes extends ConsumerWidget {
  const _Classes({required this.businessId, required this.timezone});

  final String businessId;
  final String timezone;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final api = ref.read(apiClientProvider);
    final base = '/api/owner/businesses/$businessId/slots';
    void reload() => ref.invalidate(slotsProvider(businessId));
    final names = {for (final s in ref.watch(ownerServicesProvider(businessId)).valueOrNull ?? const <Map<String, dynamic>>[]) '${s['id']}': '${s['name']}'};

    return PageScroll(maxWidth: 820, children: [
      Text('Class sessions', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text('Sessions are made from your opening hours for each group class.', style: text.bodyLarge?.copyWith(color: Palette.muted)),
      const SizedBox(height: Space.lg),
      BusyButton(
        label: 'Open sessions for the next 7 days',
        icon: Icons.event_repeat_rounded,
        onPressed: () async {
          if (await runSave(context, () => api.post('$base/generate', body: {'days': 7}), done: 'Sessions opened.')) reload();
        },
      ),
      const SizedBox(height: Space.xl),
      AsyncView<List<Map<String, dynamic>>>(
        value: ref.watch(slotsProvider(businessId)),
        onRetry: reload,
        data: (slots) {
          if (slots.isEmpty) {
            return const EmptyState(
              icon: Icons.groups_2_outlined,
              title: 'No sessions yet',
              message: 'Add a group class in Services, then open sessions here.',
            );
          }
          final sorted = [...slots]..sort((a, b) => '${a['starts_at']}'.compareTo('${b['starts_at']}'));
          return Column(children: [
            for (final slot in sorted)
              Padding(
                padding: const EdgeInsets.only(bottom: Space.sm),
                child: Panel(
                  padding: const EdgeInsets.all(Space.lg),
                  child: Row(children: [
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(names['${slot['service_id']}'] ?? 'Class', style: text.titleMedium),
                        Text(formatDayTime(DateTime.parse('${slot['starts_at']}'), timezone), style: text.bodySmall),
                        const SizedBox(height: 6),
                        StatusPill(
                          slot['is_blocked'] == true ? 'Blocked' : '${slot['booked_count']} of ${slot['capacity']} booked',
                          state: slot['is_blocked'] == true
                              ? MoneyState.charged
                              : (slot['booked_count'] == slot['capacity'] ? MoneyState.released : MoneyState.held),
                        ),
                      ]),
                    ),
                    TextButton(
                      onPressed: () async {
                        final block = slot['is_blocked'] != true;
                        if (await runSave(context, () => api.patch('$base/${slot['id']}', body: {'is_blocked': block}),
                            done: block ? 'Blocked: no new bookings.' : 'Open again.')) {
                          reload();
                        }
                      },
                      child: Text(slot['is_blocked'] == true ? 'Unblock' : 'Block'),
                    ),
                  ]),
                ),
              ),
          ]);
        },
      ),
    ]);
  }
}
