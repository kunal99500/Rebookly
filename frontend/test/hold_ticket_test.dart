import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rebookly_frontend/app/theme.dart';
import 'package:rebookly_frontend/shared/hold_ticket.dart';
import 'package:rebookly_frontend/shared/money_state.dart';

void main() {
  testWidgets('the hold ticket shows what is held, what is paid later, and the rules', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: buildTheme(),
      home: const Scaffold(
        body: SingleChildScrollView(
          child: HoldTicket(
            title: 'Haircut',
            lines: ['Tue 18 Nov, 4:30 PM'],
            held: '₹80.00',
            payLater: '₹220.00',
            steps: [
              PolicyStep(label: 'Free to cancel', detail: 'Until Mon, 4:30 PM', state: MoneyState.released),
              PolicyStep(label: 'Missed', detail: 'Up to ₹80 kept', state: MoneyState.problem),
            ],
          ),
        ),
      ),
    ));

    expect(find.text('₹80.00'), findsOneWidget);
    expect(find.text('held now, not charged'), findsOneWidget);
    expect(find.text('₹220.00'), findsOneWidget);
    expect(find.text('Free to cancel'), findsOneWidget);
    expect(find.text('Up to ₹80 kept'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
