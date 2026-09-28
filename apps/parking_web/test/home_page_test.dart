import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:parking_web/data/parking_snapshot.dart';
import 'package:parking_web/main.dart';
import 'package:parking_web/widgets/area_card.dart';

void main() {
  void viewport(WidgetTester tester, Size size) {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = size;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  test('demo totals are derived from the two areas', () {
    expect(demoSnapshot.capacity, 78);
    expect(demoSnapshot.occupied, 52);
    expect(demoSnapshot.available, 26);
    expect(demoSnapshot.areas.first.available, 2);
    expect(demoSnapshot.areas.last.available, 24);
    expect(demoSnapshot.occupancy, closeTo(2 / 3, .0001));
  });

  test('empty, fully occupied and zero capacity have finite fractions', () {
    for (final occupied in [0, 9]) {
      final area = ParkingArea(
        id: 'a',
        name: 'Area',
        capacity: 9,
        occupied: occupied,
      );
      final snapshot = ParkingSnapshot(areas: [area]);
      expect(snapshot.available, 9 - occupied);
      expect(snapshot.occupancy, occupied / 9);
    }
    const zero = ParkingSnapshot(
      areas: [ParkingArea(id: 'zero', name: 'Area', capacity: 0, occupied: 0)],
    );
    expect(zero.occupancy, 0);
    expect(zero.areas.single.occupancy, 0);
    expect(zero.available, 0);
    expect(const ParkingSnapshot(areas: []).occupancy, 0);
  });

  for (final size in [
    const Size(1440, 1100),
    const Size(768, 1024),
    const Size(390, 844),
    const Size(320, 740),
  ]) {
    testWidgets('consistent counts and responsive layout at ${size.width}', (
      tester,
    ) async {
      viewport(tester, size);
      await tester.pumpWidget(const ParkingApp(snapshot: demoSnapshot));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(
        tester.widget<Text>(find.byKey(const Key('total-available'))).data,
        '26',
      );
      expect(
        tester
            .widget<Text>(find.byKey(const Key('occupancy-count')))
            .textSpan!
            .toPlainText(),
        '52 / 78',
      );
      expect(find.text('7/9 occupied'), findsOneWidget);
      expect(find.text('45/69 occupied'), findsOneWidget);
      expect(find.text('Demo data'), findsOneWidget);
      final first = tester.getRect(find.byType(AreaCard).first);
      final second = tester.getRect(find.byType(AreaCard).last);
      if (size.width >= 768) {
        expect(first.top, second.top);
        expect(first.right, lessThan(second.left));
      } else {
        expect(first.bottom, lessThan(second.top));
        expect(first.left, second.left);
      }
      expect(first.left, greaterThanOrEqualTo(0));
      expect(second.right, lessThanOrEqualTo(size.width));
    });
  }

  testWidgets('button scrolls to areas and gives the heading keyboard focus', (
    tester,
  ) async {
    viewport(tester, const Size(390, 844));
    await tester.pumpWidget(const ParkingApp(snapshot: demoSnapshot));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('View parking areas'));
    await tester.tap(find.text('View parking areas'));
    await tester.pumpAndSettle();
    expect(
      tester.getTopLeft(find.text('Availability by area')).dy,
      lessThan(200),
    );
    expect(
      FocusManager.instance.primaryFocus!.debugLabel,
      'Availability by area',
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('demo explanation can open and close with keyboard', (
    tester,
  ) async {
    viewport(tester, const Size(1440, 1100));
    await tester.pumpWidget(const ParkingApp(snapshot: demoSnapshot));
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(find.text('A preview of easier parking'), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(find.text('A preview of easier parking'), findsNothing);
  });

  testWidgets('reduced motion shows final values on the first frame', (
    tester,
  ) async {
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    await tester.pumpWidget(const ParkingApp(snapshot: demoSnapshot));
    expect(
      tester.widget<Text>(find.byKey(const Key('total-available'))).data,
      '26',
    );
    expect(
      tester
          .widget<Text>(find.byKey(const Key('occupancy-count')))
          .textSpan!
          .toPlainText(),
      '52 / 78',
    );
  });

  testWidgets('large text at phone width remains readable without overflow', (
    tester,
  ) async {
    viewport(tester, const Size(390, 844));
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(const ParkingApp(snapshot: demoSnapshot));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.byType(AreaCard).last);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('chart semantics and accessible button contrast/targets', (
    tester,
  ) async {
    viewport(tester, const Size(1440, 1100));
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(const ParkingApp(snapshot: demoSnapshot));
    await tester.pumpAndSettle();
    expect(
      tester
          .getSemantics(find.bySemanticsLabel('Total parking occupancy'))
          .value,
      '52 of 78 spaces occupied. 26 spaces available.',
    );
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    semantics.dispose();
  });

  for (final occupied in [0, 9]) {
    testWidgets(
      'renders ${occupied == 0 ? 'empty' : 'full'} area without invalid chart',
      (tester) async {
        await tester.pumpWidget(
          ParkingApp(
            snapshot: ParkingSnapshot(
              areas: [
                ParkingArea(
                  id: 'a',
                  name: 'Area',
                  capacity: 9,
                  occupied: occupied,
                ),
              ],
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(find.text('$occupied/9 occupied'), findsOneWidget);
        expect(
          find.text(occupied == 0 ? '0% full' : '100% full'),
          findsOneWidget,
        );
        if (occupied == 9) expect(find.text('Currently full'), findsOneWidget);
      },
    );
  }

  testWidgets('zero capacity has no divide-by-zero or availability promise', (
    tester,
  ) async {
    await tester.pumpWidget(
      const ParkingApp(
        snapshot: ParkingSnapshot(
          areas: [
            ParkingArea(id: 'zero', name: 'Area', capacity: 0, occupied: 0),
          ],
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('0% full'), findsOneWidget);
    expect(find.text('No spaces configured'), findsNWidgets(2));
    expect(find.text('Your next stop has room for you.'), findsNothing);
  });
}
