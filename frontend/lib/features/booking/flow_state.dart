import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

/// Where someone is in the booking flow. It all lives in the address, so the back button works,
/// a half-finished booking can be shared, and nothing is lost when someone signs in part-way.
///
///   /b/{slug}/book                              choose services
///   /b/{slug}/book?s=id1,id2                    pick a time   (add &edit=1 to change the services)
///   /b/{slug}/book?s=..&t=2026-11-18T11:00:00Z  review and pay
///   /b/{slug}/book?class=id                     choose a class session
///   /b/{slug}/book?class=id&slot=id             review and pay for a class
class FlowState {
  const FlowState({
    this.serviceIds = const [],
    this.staffFilter,
    this.time,
    this.staffId,
    this.pay,
    this.classId,
    this.slotId,
    this.editing = false,
  });

  final List<String> serviceIds;
  final String? staffFilter;   // "only show times with this person"
  final String? time;          // the exact starts_at text from the backend
  final String? staffId;       // who will do it at that time
  final String? pay;           // deposit_held or full_held
  final String? classId;
  final String? slotId;
  final bool editing;          // back on "choose services" with the earlier choice still ticked

  factory FlowState.fromQuery(Map<String, String> query) => FlowState(
        serviceIds: (query['s'] ?? '').split(',').where((id) => id.isNotEmpty).toList(),
        staffFilter: query['staff'],
        time: query['t'],
        staffId: query['with'],
        pay: query['pay'],
        classId: query['class'],
        slotId: query['slot'],
        editing: query['edit'] == '1',
      );

  Map<String, String> toQuery() => {
        if (serviceIds.isNotEmpty) 's': serviceIds.join(','),
        if (staffFilter != null) 'staff': staffFilter!,
        if (time != null) 't': time!,
        if (staffId != null) 'with': staffId!,
        if (pay != null) 'pay': pay!,
        if (classId != null) 'class': classId!,
        if (slotId != null) 'slot': slotId!,
        if (editing) 'edit': '1',
      };

  bool get isClass => classId != null;

  void go(BuildContext context, String slug) {
    final query = toQuery();
    context.go(Uri(path: '/b/$slug/book', queryParameters: query.isEmpty ? null : query).toString());
  }

  // Each step only keeps what still makes sense after it.
  FlowState withServices(List<String> ids) => FlowState(serviceIds: ids);
  FlowState editServices() => FlowState(serviceIds: serviceIds, editing: true);
  FlowState withStaffFilter(String? id) => FlowState(serviceIds: serviceIds, staffFilter: id);
  FlowState withTime(String raw, String? staff) =>
      FlowState(serviceIds: serviceIds, staffFilter: staffFilter, time: raw, staffId: staff);
  FlowState withPay(String option) => FlowState(
        serviceIds: serviceIds, staffFilter: staffFilter, time: time, staffId: staffId, pay: option,
        classId: classId, slotId: slotId,
      );
  FlowState backToTimes() => FlowState(serviceIds: serviceIds, staffFilter: staffFilter);
  static FlowState forClass(String id) => FlowState(classId: id);
  FlowState withSlot(String id) => FlowState(classId: classId, slotId: id);
  FlowState backToSessions() => FlowState(classId: classId);
}
