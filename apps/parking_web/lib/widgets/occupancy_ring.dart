import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../data/parking_snapshot.dart';
import '../theme.dart';

class OccupancyRing extends StatelessWidget {
  const OccupancyRing({
    super.key,
    required this.snapshot,
    required this.progress,
  });
  final ParkingSnapshot snapshot;
  final double progress;

  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Total parking occupancy',
    value:
        '${snapshot.occupied} of ${snapshot.capacity} spaces occupied. ${snapshot.available} spaces available.${snapshot.isDemo ? '' : ' ${snapshot.unresolved} unresolved. ${snapshot.provisionalOccupied} occupied and ${snapshot.provisionalVacant} vacant are provisional. Recorded results, not live availability.'}',
    excludeSemantics: true,
    child: SizedBox.square(
      dimension: 286,
      child: CustomPaint(
        painter: _RingPainter(
          snapshot.occupancy * progress,
          snapshot.capacity == 0
              ? 0
              : snapshot.available / snapshot.capacity * progress,
        ),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(51),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'TOTAL OCCUPANCY',
                    style: TextStyle(
                      fontSize: 10,
                      letterSpacing: 1.5,
                      color: ParkingColors.muted,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 9),
                  Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(
                          text: snapshot.hasSamples || snapshot.capacity == 0
                              ? '${(snapshot.occupied * progress).round()}'
                              : '—',
                          style: const TextStyle(
                            fontSize: 52,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -2.5,
                          ),
                        ),
                        TextSpan(
                          text: ' / ${snapshot.capacity}',
                          style: const TextStyle(
                            fontSize: 25,
                            fontWeight: FontWeight.w500,
                            color: ParkingColors.muted,
                            letterSpacing: -1,
                          ),
                        ),
                      ],
                    ),
                    key: const Key('occupancy-count'),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    snapshot.capacity == 0
                        ? 'No spaces configured'
                        : 'spaces occupied',
                    style: const TextStyle(
                      fontSize: 12,
                      color: ParkingColors.muted,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 5,
                    ),
                    decoration: BoxDecoration(
                      color: ParkingColors.paleBlue,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      snapshot.hasSamples || snapshot.capacity == 0
                          ? '${(snapshot.occupancy * progress * 100).round()}% ${snapshot.unresolved > 0 ? 'known occupied' : 'full'}'
                          : 'Awaiting results',
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        color: ParkingColors.blue,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

class _RingPainter extends CustomPainter {
  const _RingPainter(this.fraction, this.availableFraction);
  final double fraction;
  final double availableFraction;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2 - 21;
    final ring = Rect.fromCircle(center: center, radius: radius);
    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 19
      ..strokeCap = StrokeCap.butt;
    canvas.drawCircle(center, radius, stroke..color = const Color(0xFFB9C3D1));
    if (availableFraction > 0) {
      canvas.drawArc(
        ring,
        -math.pi / 2 + math.pi * 2 * fraction,
        math.pi * 2 * availableFraction,
        false,
        stroke..color = ParkingColors.mint,
      );
    }
    if (fraction > 0) {
      final gap = fraction < 1 ? math.min(.035, math.pi * fraction / 2) : 0.0;
      canvas.drawArc(
        ring,
        -math.pi / 2 + gap,
        math.pi * 2 * fraction - gap * 2,
        false,
        stroke..color = ParkingColors.blue,
      );
    }
    final tick = Paint()
      ..color = ParkingColors.border
      ..strokeWidth = 1.3;
    for (var i = 0; i < 60; i++) {
      final angle = i / 60 * math.pi * 2;
      final vector = Offset(math.cos(angle), math.sin(angle));
      canvas.drawLine(
        center + vector * (radius + 16),
        center + vector * (radius + (i % 5 == 0 ? 21 : 19)),
        tick,
      );
    }
  }

  @override
  bool shouldRepaint(_RingPainter oldDelegate) =>
      fraction != oldDelegate.fraction ||
      availableFraction != oldDelegate.availableFraction;
}
