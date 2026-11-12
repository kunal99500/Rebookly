import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../app/tokens.dart';

/// The Rebookly mark: a tiny ticket (the same shape as the hold ticket) and the wordmark.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.showWordmark = true, this.onDark = false, this.linkHome = true});

  final bool showWordmark;
  final bool onDark;
  final bool linkHome;

  @override
  Widget build(BuildContext context) {
    final mark = Row(mainAxisSize: MainAxisSize.min, children: [
      CustomPaint(
        size: const Size(30, 30),
        painter: _TicketGlyph(
          fill: onDark ? Colors.white : Palette.forest,
          cut: onDark ? Palette.forestDeep : Palette.paper,
        ),
      ),
      if (showWordmark) ...[
        const SizedBox(width: 9),
        Text(
          'rebookly',
          style: TextStyle(
            fontFamily: Fonts.display,
            fontSize: 22,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.7,
            height: 1,
            color: onDark ? Colors.white : Palette.ink,
          ),
        ),
      ],
    ]);
    if (!linkHome) return mark;
    return Semantics(
      link: true,
      label: 'Rebookly home',
      child: InkWell(
        borderRadius: BorderRadius.circular(Radii.control),
        onTap: () => context.go('/'),
        child: Padding(padding: const EdgeInsets.all(4), child: ExcludeSemantics(child: mark)),
      ),
    );
  }
}

class _TicketGlyph extends CustomPainter {
  const _TicketGlyph({required this.fill, required this.cut});

  final Color fill;
  final Color cut;

  @override
  void paint(Canvas canvas, Size size) {
    final body = RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(8));
    canvas.drawRRect(body, Paint()..color = fill);
    final notch = Paint()..color = cut;
    final middle = size.height * 0.58;
    canvas.drawCircle(Offset(0, middle), 4, notch);
    canvas.drawCircle(Offset(size.width, middle), 4, notch);
    final dash = Paint()
      ..color = cut
      ..strokeWidth = 1.6
      ..strokeCap = StrokeCap.round;
    for (var x = 7.0; x < size.width - 6; x += 5) {
      canvas.drawLine(Offset(x, middle), Offset(x + 2, middle), dash);
    }
    canvas.drawRRect(
      RRect.fromRectAndRadius(Rect.fromLTWH(7, 7, size.width * 0.42, 3.2), const Radius.circular(2)),
      dash..style = PaintingStyle.fill,
    );
  }

  @override
  bool shouldRepaint(covariant _TicketGlyph old) => old.fill != fill || old.cut != cut;
}
