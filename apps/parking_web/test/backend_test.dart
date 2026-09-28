import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parking_web/data/parking_api.dart';
import 'package:parking_web/data/parking_snapshot.dart';
import 'package:parking_web/main.dart';

Map<String, dynamic> fixture() =>
    jsonDecode(File('test/fixtures/recorded.json').readAsStringSync())
        as Map<String, dynamic>;
ParkingApi apiWith(Future<http.Response> Function(http.Request) handler) =>
    ParkingApi(
      client: MockClient(handler),
      base: Uri.parse('http://localhost:8765'),
    );
http.Response response(Map<String, dynamic> data) =>
    http.Response(jsonEncode(data), 200);

void main() {
  test(
    'Python fixture preserves final counts, sources and provisional states',
    () {
      final data = ParkingSnapshot.fromJson(fixture());
      expect(data.isDemo, isFalse);
      expect(
        [
          data.capacity,
          data.occupied,
          data.available,
          data.provisionalOccupied,
        ],
        [78, 56, 22, 6],
      );
      expect(data.areas.first.recordingId, 'chad-1');
      expect(data.areas.last.sampleSeconds, 27);
      expect(data.areas.last.processedAt!.isUtc, isTrue);
    },
  );

  test(
    'rejects inconsistent totals, missing provenance and invalid counts',
    () {
      for (final damage in [
        'total',
        'negative',
        'provisional',
        'source',
        'sample',
        'duplicate',
      ]) {
        final json = fixture();
        switch (damage) {
          case 'total':
            json['totals']['occupied'] = 1;
          case 'negative':
            json['areas'][0]['vacant'] = -1;
          case 'provisional':
            json['areas'][0]['provisional_occupied'] = 99;
          case 'source':
            json['areas'][0]['source'] = null;
          case 'sample':
            json['areas'][0]['has_sample'] = false;
          case 'duplicate':
            json['areas'][1]['id'] = 'chad';
        }
        expect(
          () => ParkingSnapshot.fromJson(json),
          throwsFormatException,
          reason: damage,
        );
      }
    },
  );

  test('unknown and uncertain do not become vacant', () {
    final json = fixture();
    json['areas'][0]['vacant'] = 4;
    json['areas'][0]['uncertain'] = 1;
    json['areas'][0]['unknown'] = 2;
    json['totals']['vacant'] = 19;
    json['totals']['uncertain'] = 1;
    json['totals']['unknown'] = 2;
    final data = ParkingSnapshot.fromJson(json);
    expect(data.available, 19);
    expect(data.unresolved, 3);
    expect(data.occupied + data.available + data.unresolved, data.capacity);
  });

  test(
    'connection failure clears counts and recovers without demo fallback',
    () async {
      var failing = false;
      final controller = ParkingController(
        apiWith(
          (_) async =>
              failing ? http.Response('unavailable', 503) : response(fixture()),
        ),
      );
      addTearDown(controller.dispose);
      await controller.refresh();
      expect(controller.snapshot!.occupied, 56);
      failing = true;
      await controller.refresh();
      expect(controller.snapshot, isNull);
      expect(controller.error, isNotNull);
      failing = false;
      await controller.refresh();
      expect(controller.snapshot!.occupied, 56);
      expect(controller.error, isNull);
    },
  );

  test(
    'out of order requests cannot relabel old counts as a new recording',
    () async {
      final old = Completer<http.Response>();
      final controller = ParkingController(
        apiWith((request) async {
          if (request.url.queryParameters['chad'] == 'chad-1') {
            return old.future;
          }
          final json = fixture();
          json['chad_recording'] = 'chad-2';
          json['areas'][0]['source']['recording_id'] = 'chad-2';
          return response(json);
        }),
      );
      addTearDown(controller.dispose);
      final first = controller.refresh();
      await controller.selectRecording('chad-2');
      old.complete(response(fixture()));
      await first;
      expect(controller.snapshot!.chadRecording, 'chad-2');
      expect(controller.loading, isFalse);
    },
  );

  test('wrong recording response is rejected', () async {
    final api = apiWith((_) async => response(fixture()));
    addTearDown(api.close);
    await expectLater(api.fetch('chad-2'), throwsFormatException);
  });

  test(
    'analysis uses guarded POST and handles an already running job',
    () async {
      var posts = 0;
      final controller = ParkingController(
        apiWith((request) async {
          if (request.method == 'POST') {
            posts++;
            expect(request.url.path, '/api/analysis');
            expect(request.headers['X-Parking-Client'], 'web');
            return http.Response('{}', 409);
          }
          final data = fixture();
          data['analysis']['status'] = 'running';
          return response(data);
        }),
      );
      addTearDown(controller.dispose);
      await controller.analyze();
      await controller.analyze();
      expect(posts, 1);
      expect(controller.actionError, isNull);
    },
  );

  for (final width in [1440.0, 768.0, 390.0, 320.0]) {
    testWidgets('recorded page agrees with backend at $width pixels', (
      tester,
    ) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = Size(width, 1100);
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        ParkingApp(api: apiWith((_) async => response(fixture()))),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Recorded data'), findsOneWidget);
      expect(find.text('Demo data'), findsNothing);
      expect(
        tester.widget<Text>(find.byKey(const Key('total-available'))).data,
        '22',
      );
      expect(
        tester
            .widget<Text>(find.byKey(const Key('occupancy-count')))
            .textSpan!
            .toPlainText(),
        '56 / 78',
      );
      expect(find.text('2/9 occupied'), findsOneWidget);
      expect(find.text('54/69 occupied'), findsOneWidget);
      expect(find.textContaining('6 occupied (P)'), findsNWidgets(2));
      expect(find.textContaining('chad-1 · sample 27s'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    });
  }

  testWidgets('unavailable backend has neutral unknown display and retry', (
    tester,
  ) async {
    await tester.pumpWidget(
      ParkingApp(api: apiWith((_) async => http.Response('failed', 503))),
    );
    await tester.pumpAndSettle();
    expect(
      tester.widget<Text>(find.byKey(const Key('total-available'))).data,
      '—',
    );
    expect(find.text('Retry connection'), findsOneWidget);
    expect(find.textContaining('78 unresolved'), findsOneWidget);
    expect(find.text('Currently full'), findsNothing);
    expect(find.text('Demo data'), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets(
    'recorded controls remain accessible with reduced motion and large text',
    (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(390, 844);
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      tester.platformDispatcher.accessibilityFeaturesTestValue =
          const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      addTearDown(
        tester.platformDispatcher.clearAccessibilityFeaturesTestValue,
      );
      await tester.pumpWidget(
        ParkingApp(api: apiWith((_) async => response(fixture()))),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(
        tester.widget<Text>(find.byKey(const Key('total-available'))).data,
        '22',
      );
      await tester.pumpWidget(const SizedBox());
    },
  );
}
