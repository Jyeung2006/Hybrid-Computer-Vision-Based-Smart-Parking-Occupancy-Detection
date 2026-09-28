import 'package:flutter/material.dart';
import '../data/parking_snapshot.dart';
import '../theme.dart';

class AreaCard extends StatefulWidget {
  const AreaCard({super.key, required this.area});
  final ParkingArea area;
  @override
  State<AreaCard> createState() => _AreaCardState();
}

class _AreaCardState extends State<AreaCard> {
  bool hovered = false;

  @override
  Widget build(BuildContext context) {
    final area = widget.area;
    final overhead = area.id == 'overhead';
    return MouseRegion(
      onEnter: (_) => setState(() => hovered = true),
      onExit: (_) => setState(() => hovered = false),
      child: AnimatedContainer(
        duration: MediaQuery.disableAnimationsOf(context)
            ? Duration.zero
            : const Duration(milliseconds: 180),
        padding: const EdgeInsets.all(26),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(
            color: hovered ? const Color(0xFFB6C7F8) : ParkingColors.border,
          ),
          boxShadow: [
            BoxShadow(
              color: ParkingColors.navy.withValues(
                alpha: hovered ? .055 : .018,
              ),
              blurRadius: hovered ? 25 : 12,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: overhead
                              ? ParkingColors.paleMint
                              : ParkingColors.paleBlue,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          overhead
                              ? Icons.grid_view_rounded
                              : Icons.local_parking_rounded,
                          size: 21,
                          color: overhead
                              ? ParkingColors.green
                              : ParkingColors.blue,
                        ),
                      ),
                      const SizedBox(height: 15),
                      Text(
                        area.name,
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -.5,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${area.capacity} total spaces',
                        style: const TextStyle(
                          fontSize: 12,
                          color: ParkingColors.muted,
                        ),
                      ),
                    ],
                  ),
                ),
                if (MediaQuery.textScalerOf(context).scale(1) <= 1.4)
                  ExcludeSemantics(
                    child: SizedBox(
                      width: 112,
                      height: 103,
                      child: CustomPaint(
                        painter: _ParkingIllustration(overhead: overhead),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 24),
            Semantics(
              label:
                  '${area.name}: ${area.available} spaces left, ${area.occupied} of ${area.capacity} occupied',
              excludeSemantics: true,
              child: Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 9,
                children: [
                  Text(
                    area.hasSample ? '${area.available}' : '—',
                    key: Key('${area.id}-available'),
                    style: TextStyle(
                      fontSize: 31,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -1,
                      color: area.available > 0
                          ? ParkingColors.green
                          : ParkingColors.navy,
                    ),
                  ),
                  const Text(
                    'spaces left',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                  ),
                  const Text('|', style: TextStyle(color: ParkingColors.muted)),
                  Text(
                    '${area.hasSample ? area.occupied : '—'}/${area.capacity} occupied',
                    key: Key('${area.id}-occupied'),
                    style: const TextStyle(
                      color: ParkingColors.muted,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 15),
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: Semantics(
                label:
                    '${area.name}: ${area.occupied} occupied, ${area.available} vacant, ${area.unresolved} unresolved',
                child: SizedBox(
                  height: 7,
                  child: Row(
                    children: [
                      if (area.occupied > 0)
                        Expanded(
                          flex: area.occupied,
                          child: Container(color: ParkingColors.blue),
                        ),
                      if (area.available > 0)
                        Expanded(
                          flex: area.available,
                          child: Container(color: ParkingColors.mint),
                        ),
                      if (area.unresolved > 0 || area.capacity == 0)
                        Expanded(
                          flex: area.unresolved > 0 ? area.unresolved : 1,
                          child: Container(color: const Color(0xFFB9C3D1)),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 13),
            Row(
              children: [
                Icon(
                  area.capacity == 0
                      ? Icons.info_outline_rounded
                      : area.available == 0
                      ? Icons.remove_circle_outline_rounded
                      : Icons.check_circle_outline_rounded,
                  size: 14,
                  color: area.available > 0
                      ? ParkingColors.green
                      : ParkingColors.muted,
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    !area.hasSample
                        ? 'No valid recorded sample'
                        : area.unresolved > 0
                        ? '${area.unresolved} unresolved · not available'
                        : area.capacity == 0
                        ? 'No spaces configured'
                        : area.available == 0
                        ? (area.recordingId == null
                              ? 'Currently full'
                              : 'No vacant spaces in this sample')
                        : 'Spaces available',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: area.available > 0
                          ? ParkingColors.green
                          : ParkingColors.muted,
                    ),
                  ),
                ),
              ],
            ),
            if (area.provisionalOccupied > 0 || area.provisionalVacant > 0)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Text(
                  '${area.provisionalOccupied} occupied (P) · ${area.provisionalVacant} vacant (P)',
                  style: const TextStyle(
                    fontSize: 12,
                    color: ParkingColors.muted,
                  ),
                ),
              ),
            if (area.recordingId != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  '${area.recordingId} · sample ${area.sampleSeconds?.toStringAsFixed(0)}s\nAnalyzed ${_localTime(area.processedAt!)} (local)',
                  style: const TextStyle(
                    fontSize: 11,
                    height: 1.7,
                    color: ParkingColors.muted,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

String _localTime(DateTime date) {
  final value = date.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${value.year}-${two(value.month)}-${two(value.day)} ${two(value.hour)}:${two(value.minute)}:${two(value.second)}';
}

/// Decorative illustration, not a geographic map or per-bay occupancy diagram.
class _ParkingIllustration extends CustomPainter {
  const _ParkingIllustration({required this.overhead});
  final bool overhead;
  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.translate(size.width / 2, size.height / 2);
    canvas.rotate(overhead ? -.08 : .07);
    canvas.scale(size.width / 150, size.height / 110);
    final paint = Paint();
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(-68, -44, 136, 88),
        const Radius.circular(15),
      ),
      paint
        ..color = overhead ? const Color(0xFFEAF6F2) : const Color(0xFFF0F4FC),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(-57, -31, 114, 62),
        const Radius.circular(4),
      ),
      paint..color = const Color(0xFFDBE4F2),
    );
    for (var i = 0; i < 5; i++) {
      canvas.drawRect(
        Rect.fromLTWH(-46 + i * 21, -1, 10, 2),
        paint..color = Colors.white,
      );
    }
    for (var row = 0; row < 2; row++) {
      for (var col = 0; col < 5; col++) {
        final x = -54.0 + col * 22;
        final y = row == 0 ? -29.0 : 10.0;
        canvas.drawRect(
          Rect.fromLTWH(x, y, 20, 20),
          paint..color = const Color(0xFFF9FBFF),
        );
        final occupied = overhead ? (col + row) % 3 != 0 : col != 3;
        if (occupied) {
          canvas.drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromLTWH(x + 4, y + 1, 12, 18),
              const Radius.circular(3),
            ),
            paint
              ..color = col % 2 == 0
                  ? const Color(0xFF7294EE)
                  : const Color(0xFF94ADCA),
          );
          canvas.drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromLTWH(x + 5.5, y + 5, 9, 6),
              const Radius.circular(2),
            ),
            paint..color = const Color(0xFFDDEAFF),
          );
        } else {
          canvas.drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromLTWH(x + 3, y + 2, 14, 16),
              const Radius.circular(3),
            ),
            paint..color = const Color(0xFFB8EBD9),
          );
        }
      }
    }
    canvas.drawCircle(
      const Offset(61, -38),
      11,
      paint..color = const Color(0xFFC6ECDD),
    );
    canvas.drawCircle(
      const Offset(64, -41),
      7,
      paint..color = const Color(0xFF9CD4BD),
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(_ParkingIllustration oldDelegate) =>
      overhead != oldDelegate.overhead;
}
