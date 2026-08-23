import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:robobtc_mobile/main.dart';

void main() {
  testWidgets('RoboBTC app loads', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: RoboBTCApp()));
    await tester.pump();

    expect(find.byType(Scaffold), findsOneWidget);
    expect(find.byType(BottomNavigationBar), findsWidgets);
  });
}
