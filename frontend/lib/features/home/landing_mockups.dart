import 'package:flutter/material.dart';

import '../../app/tokens.dart';
import '../../core/i18n/i18n.dart';
import '../../shared/layout.dart';

/// Small, real-looking pieces of the app used on the landing page (instead of stock photos).

const _frame = Color(0xFF1D2622);

TextStyle _s(BuildContext context, {double size = 11, FontWeight weight = FontWeight.w400, Color color = Palette.ink}) =>
    TextStyle(fontFamily: Fonts.body, fontSize: size, fontWeight: weight, color: color, height: 1.3);

class _Tag extends StatelessWidget {
  const _Tag(this.label, this.color, this.background);

  final String label;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(Radii.chip)),
        child: Text(label, style: _s(context, size: 9.5, weight: FontWeight.w600, color: color)),
      );
}

Widget _apptRow(BuildContext context, String time, String who, bool confirmed) => Container(
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: const BoxDecoration(border: Border(top: BorderSide(color: Palette.line))),
      child: Row(children: [
        SizedBox(width: 54, child: Text(time, style: _s(context, size: 10))),
        Expanded(child: Text(who, style: _s(context, size: 10), overflow: TextOverflow.ellipsis)),
        confirmed
            ? _Tag(context.tr('mock.confirmed'), Palette.released, Palette.releasedBg)
            : _Tag(context.tr('mock.pending'), Palette.waiting, Palette.waitingBg),
      ]),
    );

class _Laptop extends StatelessWidget {
  const _Laptop({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          decoration: BoxDecoration(
            color: Palette.surface,
            border: Border.all(color: _frame, width: 9),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(14), bottom: Radius.circular(5)),
            boxShadow: const [BoxShadow(color: Color(0x3315382D), blurRadius: 40, offset: Offset(0, 20))],
          ),
          child: ClipRRect(borderRadius: BorderRadius.circular(5), child: child),
        ),
        FractionallySizedBox(
          widthFactor: 1.08,
          child: Container(
            height: 12,
            decoration: const BoxDecoration(
              gradient: LinearGradient(colors: [Color(0xFFC9D0CC), Color(0xFF9AA39E)], begin: Alignment.topCenter, end: Alignment.bottomCenter),
              borderRadius: BorderRadius.vertical(bottom: Radius.circular(12)),
            ),
          ),
        ),
      ]);
}

class _Phone extends StatelessWidget {
  const _Phone({required this.child, this.width = 224});

  final Widget child;
  final double width;

  @override
  Widget build(BuildContext context) => Container(
        width: width,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: _frame,
          borderRadius: BorderRadius.circular(32),
          boxShadow: const [BoxShadow(color: Color(0x4015382D), blurRadius: 40, offset: Offset(0, 20))],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(25),
          child: ColoredBox(color: Palette.surface, child: child),
        ),
      );
}

class _PlacePhoto extends StatelessWidget {
  const _PlacePhoto({this.height = 82});

  final double height;

  @override
  Widget build(BuildContext context) => Container(
        height: height,
        decoration: const BoxDecoration(gradient: LinearGradient(colors: [Color(0xFFC9DCCF), Color(0xFF8FB3A0)])),
        alignment: Alignment.bottomRight,
        padding: const EdgeInsets.all(12),
        child: Container(width: 54, height: 38, decoration: BoxDecoration(color: const Color(0x8CFFFFFF), borderRadius: BorderRadius.circular(8))),
      );
}

Widget _primary(BuildContext context, String label) => Container(
      margin: const EdgeInsets.fromLTRB(10, 8, 10, 10),
      padding: const EdgeInsets.symmetric(vertical: 7),
      alignment: Alignment.center,
      decoration: BoxDecoration(color: Palette.forest, borderRadius: BorderRadius.circular(9)),
      child: Text(label, style: _s(context, size: 11, weight: FontWeight.w600, color: Colors.white)),
    );

// ---------- hero: phone (client app) over laptop (business dashboard) ----------

class HeroDevices extends StatelessWidget {
  const HeroDevices({super.key});

  @override
  Widget build(BuildContext context) {
    final animate = !reduceMotion(context);
    final narrow = MediaQuery.sizeOf(context).width < 520;
    final scene = SizedBox(
      height: narrow ? 440 : 480,
      child: LayoutBuilder(builder: (context, constraints) {
        return Stack(clipBehavior: Clip.hardEdge, children: [
          Positioned(right: 0, top: narrow ? 70 : 56, width: constraints.maxWidth * (narrow ? 0.86 : 0.76), child: const _Dashboard()),
          Positioned(left: 4, top: 6, child: Transform.rotate(angle: -0.07, child: _ClientHome(width: narrow ? 196 : 222))),
        ]);
      }),
    );
    if (!animate) return scene;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 900),
      curve: Curves.easeOutCubic,
      builder: (context, t, child) => Opacity(opacity: t, child: Transform.translate(offset: Offset(0, 28 * (1 - t)), child: child)),
      child: scene,
    );
  }
}

class _Dashboard extends StatelessWidget {
  const _Dashboard();

  @override
  Widget build(BuildContext context) {
    Widget stat(String n, String label, Color bg) => Expanded(
          child: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(10), border: Border.all(color: Palette.line)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(n, style: const TextStyle(fontFamily: Fonts.display, fontWeight: FontWeight.w800, fontSize: 20, color: Palette.ink, height: 1.1)),
              Text(label, style: _s(context, size: 9.5), overflow: TextOverflow.ellipsis),
            ]),
          ),
        );
    return _Laptop(
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          width: 96,
          height: 250,
          color: Palette.paper,
          padding: const EdgeInsets.all(10),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('rebookly', style: const TextStyle(fontFamily: Fonts.display, fontWeight: FontWeight.w800, fontSize: 13, color: Palette.ink)),
            const SizedBox(height: 10),
            for (final (i, key) in const ['mock.dashboard', 'mock.appointments', 'mock.services', 'mock.staff', 'mock.payments'].indexed)
              Container(
                margin: const EdgeInsets.only(bottom: 2),
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
                decoration: BoxDecoration(color: i == 0 ? Palette.sage : null, borderRadius: BorderRadius.circular(6)),
                child: Text(context.tr(key), style: _s(context, size: 9.5, weight: i == 0 ? FontWeight.w600 : FontWeight.w400, color: i == 0 ? Palette.forest : Palette.muted)),
              ),
          ]),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(context.tr('mock.business_dashboard'), style: _s(context, size: 12, weight: FontWeight.w700)),
              Text(context.tr('mock.todays_overview'), style: _s(context, size: 10, color: Palette.muted)),
              const SizedBox(height: 6),
              Row(children: [
                stat('24', context.tr('mock.appointments'), Palette.heldBg),
                const SizedBox(width: 6),
                stat('18', context.tr('mock.confirmed'), Palette.releasedBg),
                const SizedBox(width: 6),
                stat('2', context.tr('mock.cancellations'), Palette.problemBg),
              ]),
              const SizedBox(height: 10),
              Text(context.tr('mock.todays_appointments'), style: _s(context, size: 11, weight: FontWeight.w700)),
              const SizedBox(height: 4),
              _apptRow(context, '10:00 AM', context.tr('mock.appt1'), true),
              _apptRow(context, '11:30 AM', context.tr('mock.appt2'), true),
              _apptRow(context, '2:00 PM', context.tr('mock.appt3'), false),
            ]),
          ),
        ),
      ]),
    );
  }
}

class _ClientHome extends StatelessWidget {
  const _ClientHome({required this.width});

  final double width;

  @override
  Widget build(BuildContext context) {
    const cats = [(Icons.content_cut_rounded, 'mock.salon'), (Icons.spa_outlined, 'mock.spa'), (Icons.face_retouching_natural, 'mock.barber'), (Icons.self_improvement_rounded, 'mock.wellness')];
    return _Phone(
      width: width,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, mainAxisSize: MainAxisSize.min, children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(14, 16, 14, 6),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(context.tr('mock.hi'), style: const TextStyle(fontFamily: Fonts.display, fontWeight: FontWeight.w800, fontSize: 18, color: Palette.ink)),
            Text(context.tr('mock.find_near'), style: _s(context, size: 10, color: Palette.muted)),
          ]),
        ),
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: Palette.paper, borderRadius: BorderRadius.circular(10), border: Border.all(color: Palette.line)),
          child: Text(context.tr('mock.search'), style: _s(context, size: 10, color: Palette.faint), overflow: TextOverflow.ellipsis),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
            for (final (icon, key) in cats)
              Column(children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(11)),
                  child: Icon(icon, size: 17, color: Palette.forest),
                ),
                const SizedBox(height: 3),
                Text(context.tr(key), style: _s(context, size: 9)),
              ]),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(14, 8, 14, 0),
          child: Row(children: [
            Expanded(child: Text(context.tr('mock.popular'), style: _s(context, size: 11, weight: FontWeight.w700))),
            Text(context.tr('mock.view_all'), style: _s(context, size: 10, color: Palette.forest, weight: FontWeight.w600)),
          ]),
        ),
        Container(
          margin: const EdgeInsets.all(12),
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), border: Border.all(color: Palette.line)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const _PlacePhoto(),
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 0),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(context.tr('mock.studio'), style: _s(context, size: 12, weight: FontWeight.w700)),
                Text(context.tr('mock.studio_meta'), style: _s(context, size: 9.5, color: Palette.muted)),
              ]),
            ),
            _primary(context, context.tr('mock.book_now')),
          ]),
        ),
        Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: const BoxDecoration(border: Border(top: BorderSide(color: Palette.line))),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
            for (final (i, key) in const ['nav.home', 'nav.bookings', 'nav.explore', 'account.profile'].indexed)
              Text(context.tr(key), style: _s(context, size: 9, weight: i == 0 ? FontWeight.w700 : FontWeight.w400, color: i == 0 ? Palette.forest : Palette.muted)),
          ]),
        ),
      ]),
    );
  }
}

// ---------- the problem: two small scenes ----------

class ClientScene extends StatelessWidget {
  const ClientScene({super.key});

  @override
  Widget build(BuildContext context) {
    Widget mine(String key) => Align(
          alignment: Alignment.centerRight,
          child: Container(
            margin: const EdgeInsets.only(bottom: 6),
            constraints: const BoxConstraints(maxWidth: 300),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
            decoration: BoxDecoration(color: Palette.forest, borderRadius: BorderRadius.circular(14)),
            child: Text(context.tr(key), style: _s(context, size: 13, color: Colors.white)),
          ),
        );
    Widget system(String key) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Center(child: Text(context.tr(key), style: _s(context, size: 12, color: Palette.muted))),
        );
    return Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      mine('mock.msg1'),
      system('mock.no_answer'),
      mine('mock.msg2'),
      system('mock.seen'),
    ]);
  }
}

class BusinessScene extends StatelessWidget {
  const BusinessScene({super.key});

  @override
  Widget build(BuildContext context) {
    Widget slot(String key, String tagKey, bool came) => Container(
          margin: const EdgeInsets.only(bottom: 6),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          decoration: BoxDecoration(
            color: came ? Palette.surface : Colors.transparent,
            borderRadius: BorderRadius.circular(10),
            border: came ? null : Border.all(color: const Color(0x8C9A5F0B), width: 1.5),
          ),
          child: Row(children: [
            Expanded(child: Text(context.tr(key), style: _s(context, size: 13, color: came ? Palette.ink : Palette.waiting))),
            came
                ? _Tag(context.tr(tagKey), Palette.released, Palette.releasedBg)
                : Text(context.tr(tagKey), style: _s(context, size: 12, color: Palette.waiting, weight: FontWeight.w600)),
          ]),
        );
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, mainAxisAlignment: MainAxisAlignment.center, children: [
      slot('mock.slot1', 'mock.came', true),
      slot('mock.slot2', 'mock.no_show', false),
      slot('mock.slot3', 'mock.cancelled_late', false),
      slot('mock.slot4', 'mock.came', true),
      Text(context.tr('mock.lost'), style: _s(context, size: 12, color: Palette.waiting, weight: FontWeight.w700)),
    ]);
  }
}

// ---------- the solution: booking on a phone, appointments on a laptop ----------

class BookingPhone extends StatelessWidget {
  const BookingPhone({super.key});

  @override
  Widget build(BuildContext context) {
    Widget label(String key) => Padding(
          padding: const EdgeInsets.fromLTRB(10, 8, 10, 4),
          child: Text(context.tr(key), style: _s(context, size: 10.5, weight: FontWeight.w700)),
        );
    return Center(
      child: _Phone(
        width: 214,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, mainAxisSize: MainAxisSize.min, children: [
          const _PlacePhoto(height: 88),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 6),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(context.tr('mock.studio'), style: _s(context, size: 12, weight: FontWeight.w700)),
              Text(context.tr('mock.studio_reviews'), style: _s(context, size: 9.5, color: Palette.muted)),
            ]),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: const BoxDecoration(border: Border(top: BorderSide(color: Palette.line))),
            child: Row(children: [
              Expanded(child: Text(context.tr('mock.haircut_styling'), style: _s(context, size: 11, weight: FontWeight.w700))),
              Text('₹1,200', style: _s(context, size: 11, weight: FontWeight.w700)),
            ]),
          ),
          label('mock.select_date'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10),
            child: Row(children: [
              for (final (day, date, on) in const [('Tue', '20', false), ('Wed', '21', true), ('Thu', '22', false), ('Fri', '23', false)])
                Expanded(
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 2),
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    decoration: BoxDecoration(
                      color: on ? Palette.forest : null,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: on ? Palette.forest : Palette.line),
                    ),
                    child: Column(children: [
                      Text(day, style: _s(context, size: 9, color: on ? Colors.white : Palette.muted)),
                      Text(date, style: _s(context, size: 12, weight: FontWeight.w700, color: on ? Colors.white : Palette.ink)),
                    ]),
                  ),
                ),
            ]),
          ),
          label('mock.available_time'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10),
            child: Wrap(spacing: 5, runSpacing: 5, children: [
              for (final (time, on) in const [('10:00 AM', false), ('11:30 AM', true), ('1:00 PM', false)])
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
                  decoration: BoxDecoration(
                    color: on ? Palette.sage : null,
                    borderRadius: BorderRadius.circular(7),
                    border: Border.all(color: on ? Palette.forest : Palette.line),
                  ),
                  child: Text(time, style: _s(context, size: 9.5, weight: on ? FontWeight.w600 : FontWeight.w400, color: on ? Palette.forest : Palette.ink)),
                ),
            ]),
          ),
          _primary(context, context.tr('mock.book_appointment')),
        ]),
      ),
    );
  }
}

class AppointmentsLaptop extends StatelessWidget {
  const AppointmentsLaptop({super.key});

  @override
  Widget build(BuildContext context) => _Laptop(
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(context.tr('mock.appointments'), style: _s(context, size: 12, weight: FontWeight.w700)),
            const SizedBox(height: 6),
            Row(children: [
              _Tag(context.tr('demo.today'), Palette.held, Palette.heldBg),
              const SizedBox(width: 8),
              Text(context.tr('mock.upcoming'), style: _s(context, size: 10, color: Palette.muted)),
              const SizedBox(width: 8),
              Text(context.tr('mock.past'), style: _s(context, size: 10, color: Palette.muted)),
            ]),
            const SizedBox(height: 6),
            _apptRow(context, '10:00 AM', 'Priya S.', true),
            _apptRow(context, '11:30 AM', 'Anjali K.', true),
            _apptRow(context, '2:00 PM', 'Meera T.', false),
          ]),
        ),
      );
}
