import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parking_web/replay_page.dart';

Map<String, dynamic> fixture() => {
  'mode': 'replay',
  'simulation': true,
  'live_availability': false,
  'status': 'playing',
  'message': 'Replaying chad-1',
  'source_id': 'chad-1',
  'capacity': 2,
  'available': 1,
  'provisional_occupied': 1,
  'counts': {'occupied': 1, 'vacant': 1, 'unknown': 0, 'stale': 0},
  'bays': [
    {
      'bay_id': 'B01',
      'state': 'vacant',
      'available': true,
      'fresh': true,
      'provisional': false,
      'source': 'reference',
      'candidate_streak': 3,
    },
    {
      'bay_id': 'B02',
      'state': 'occupied',
      'available': false,
      'fresh': true,
      'provisional': true,
      'source': 'yolov8',
      'candidate_streak': 1,
    },
  ],
};

void main() {
  test('rejects mismatched counts and never accepts a live flag', () {
    expect(validateReplaySnapshot(fixture())['available'], 1);
    final wrong = fixture();
    wrong['available'] = 2;
    expect(() => validateReplaySnapshot(wrong), throwsFormatException);
    final live = fixture();
    live['live_availability'] = true;
    expect(() => validateReplaySnapshot(live), throwsFormatException);
  });

  testWidgets('shows historical area counts and provisional bay', (
    tester,
  ) async {
    final client = MockClient(
      (_) async => http.Response(jsonEncode(fixture()), 200),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: ReplayPage(
          client: client,
          base: Uri.parse('http://localhost:8765'),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.text(
        'Simulation, not live availability. Frame times are positions in historical footage; the original capture time is unknown.',
      ),
      findsOneWidget,
    );
    expect(find.text('Historically available'), findsOneWidget);
    expect(find.text('OCCUPIED (P)'), findsOneWidget);
    expect(find.text('B01'), findsOneWidget);
  });

  for (final width in [320.0, 390.0, 768.0, 1440.0]) {
    testWidgets('replay controls and bays fit ${width.toInt()}px', (tester) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final client = MockClient((_) async => http.Response(jsonEncode(fixture()), 200));
      await tester.pumpWidget(MaterialApp(home: ReplayPage(client: client,
        base: Uri.parse('http://localhost:8765'))));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
}
