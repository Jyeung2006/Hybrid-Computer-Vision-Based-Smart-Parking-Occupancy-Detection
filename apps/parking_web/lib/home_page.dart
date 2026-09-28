import 'package:flutter/material.dart';
import 'data/parking_snapshot.dart';
import 'theme.dart';
import 'widgets/area_card.dart';
import 'widgets/occupancy_ring.dart';

class ParkingHomePage extends StatefulWidget {
  const ParkingHomePage({
    super.key,
    required this.snapshot,
    this.connectionPanel,
  });
  final ParkingSnapshot snapshot;
  final Widget? connectionPanel;
  @override
  State<ParkingHomePage> createState() => _ParkingHomePageState();
}

class _ParkingHomePageState extends State<ParkingHomePage>
    with SingleTickerProviderStateMixin {
  late final AnimationController entrance = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 650),
  );
  final areasKey = GlobalKey();
  final areasFocus = FocusNode(debugLabel: 'Availability by area');
  bool started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      entrance.value = 1;
    } else if (!started) {
      entrance.forward();
    }
    started = true;
  }

  @override
  void dispose() {
    entrance.dispose();
    areasFocus.dispose();
    super.dispose();
  }

  void viewAreas() {
    final target = areasKey.currentContext;
    if (target == null) return;
    areasFocus.requestFocus();
    Scrollable.ensureVisible(
      target,
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : const Duration(milliseconds: 450),
      curve: Curves.easeInOutCubic,
      alignment: .08,
    );
  }

  void showDemoInfo() => showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(
        widget.snapshot.isDemo
            ? 'A preview of easier parking'
            : 'About these recorded results',
      ),
      content: Text(
        widget.snapshot.isDemo
            ? 'These are sample counts for the home page design. They are not connected to a camera or live parking feed.\n\nCHAD has 9 demo spaces and Overhead has 69. Availability is calculated from the same counts shown in the chart.'
            : 'Counts come from the Python system’s Final decisions for the selected CHAD recording and the Overhead recording. These recordings cover different periods, so the combined total is not live availability.\n\nProvisional occupied results count as occupied and are labelled separately. Uncertain and unknown bays never count as available. Each card shows the recording position and analysis time.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Got it'),
        ),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final snapshot = widget.snapshot;
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          key: const Key('home-scroll'),
          child: Column(
            children: [
              _Header(onDemoPressed: showDemoInfo, isDemo: snapshot.isDemo),
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1176),
                  child: Padding(
                    padding: EdgeInsets.symmetric(
                      horizontal: MediaQuery.sizeOf(context).width < 600
                          ? 20
                          : 32,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 43),
                        const _Intro(),
                        const SizedBox(height: 29),
                        if (widget.connectionPanel != null) ...[
                          widget.connectionPanel!,
                          const SizedBox(height: 22),
                        ],
                        AnimatedBuilder(
                          animation: entrance,
                          builder: (context, _) {
                            final t = Curves.easeOutCubic.transform(
                              entrance.value,
                            );
                            return Opacity(
                              opacity: .25 + .75 * t,
                              child: Transform.translate(
                                offset: Offset(0, 12 * (1 - t)),
                                child: _OverviewCard(
                                  snapshot: snapshot,
                                  progress: t,
                                  onViewAreas: viewAreas,
                                ),
                              ),
                            );
                          },
                        ),
                        const SizedBox(height: 39),
                        Focus(
                          focusNode: areasFocus,
                          child: Semantics(
                            header: true,
                            child: Column(
                              key: areasKey,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Availability by area',
                                  style: TextStyle(
                                    fontSize: 23,
                                    fontWeight: FontWeight.w800,
                                    letterSpacing: -.6,
                                  ),
                                ),
                                const SizedBox(height: 5),
                                Text(
                                  snapshot.isDemo
                                      ? 'A quick look at where you can park.'
                                      : 'Latest analyzed sample for each selected recording.',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: ParkingColors.muted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 21),
                        LayoutBuilder(
                          builder: (context, constraints) {
                            final columns =
                                constraints.maxWidth >= 680 &&
                                    MediaQuery.textScalerOf(context).scale(1) <=
                                        1.4
                                ? 2
                                : 1;
                            final width =
                                (constraints.maxWidth - (columns - 1) * 22) /
                                columns;
                            return Wrap(
                              spacing: 22,
                              runSpacing: 20,
                              children: [
                                for (var i = 0; i < snapshot.areas.length; i++)
                                  SizedBox(
                                    width: width,
                                    child: AnimatedBuilder(
                                      animation: entrance,
                                      child: AreaCard(area: snapshot.areas[i]),
                                      builder: (context, child) {
                                        final delay = .08 * (i % 3 + 1);
                                        final t = Curves.easeOutCubic.transform(
                                          ((entrance.value - delay) /
                                                  (1 - delay))
                                              .clamp(0.0, 1.0),
                                        );
                                        return Opacity(
                                          opacity: t,
                                          child: Transform.translate(
                                            offset: Offset(0, (1 - t) * 16),
                                            child: child,
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                              ],
                            );
                          },
                        ),
                        const SizedBox(height: 32),
                        _Footer(isDemo: snapshot.isDemo),
                        const SizedBox(height: 28),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.onDemoPressed, required this.isDemo});
  final bool isDemo;
  final VoidCallback onDemoPressed;
  @override
  Widget build(BuildContext context) => Container(
    decoration: const BoxDecoration(
      color: Colors.white,
      border: Border(bottom: BorderSide(color: ParkingColors.border)),
    ),
    child: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1176),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 15),
          child: Row(
            children: [
              if (MediaQuery.textScalerOf(context).scale(1) <= 1.4) ...[
                Container(
                  width: 39,
                  height: 39,
                  decoration: BoxDecoration(
                    color: ParkingColors.blue,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: ParkingColors.blue.withValues(alpha: .18),
                        blurRadius: 14,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.local_parking_rounded,
                    color: Colors.white,
                    size: 26,
                  ),
                ),
                const SizedBox(width: 11),
              ],
              const Expanded(
                child: Text(
                  'Parking',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -.8,
                  ),
                ),
              ),
              Expanded(
                child: Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: onDemoPressed,
                    style: TextButton.styleFrom(
                      foregroundColor: ParkingColors.muted,
                      backgroundColor: ParkingColors.background,
                      padding: const EdgeInsets.symmetric(horizontal: 14),
                    ),
                    icon: const Icon(Icons.info_outline_rounded, size: 15),
                    label: Text(
                      isDemo ? 'Demo data' : 'Recorded data',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _Intro extends StatelessWidget {
  const _Intro();
  @override
  Widget build(BuildContext context) {
    final small = MediaQuery.sizeOf(context).width < 600;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '—  LESS SEARCHING. MORE ARRIVING.',
          style: TextStyle(
            color: ParkingColors.blue,
            fontSize: 10,
            letterSpacing: 1.5,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 13),
        Semantics(
          header: true,
          child: Text.rich(
            const TextSpan(
              children: [
                TextSpan(text: 'Find your next '),
                TextSpan(
                  text: 'parking space.',
                  style: TextStyle(color: ParkingColors.blue),
                ),
              ],
            ),
            style: TextStyle(
              fontSize: small ? 35 : 43,
              height: 1.22,
              fontWeight: FontWeight.w800,
              letterSpacing: -1.8,
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          'See what’s available. Choose your area. Park a little easier.',
          style: TextStyle(
            fontSize: 14,
            color: ParkingColors.muted,
            height: 1.7,
          ),
        ),
      ],
    );
  }
}

class _OverviewCard extends StatelessWidget {
  const _OverviewCard({
    required this.snapshot,
    required this.progress,
    required this.onViewAreas,
  });
  final ParkingSnapshot snapshot;
  final double progress;
  final VoidCallback onViewAreas;

  @override
  Widget build(BuildContext context) => Container(
    clipBehavior: Clip.antiAlias,
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(26),
      border: Border.all(color: ParkingColors.border),
      boxShadow: [
        BoxShadow(
          color: ParkingColors.navy.withValues(alpha: .025),
          blurRadius: 24,
          offset: const Offset(0, 8),
        ),
      ],
    ),
    child: LayoutBuilder(
      builder: (context, constraints) {
        final wide =
            constraints.maxWidth >= 680 &&
            MediaQuery.textScalerOf(context).scale(1) <= 1.4;
        const heading = Row(
          children: [
            Icon(
              Icons.donut_large_rounded,
              color: ParkingColors.blue,
              size: 17,
            ),
            SizedBox(width: 8),
            Flexible(
              child: Text(
                'Occupancy overview',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        );
        final information = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (wide) ...[heading, const SizedBox(height: 26)],
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              children: [
                Text(
                  snapshot.hasSamples
                      ? '${(snapshot.available * progress).round()}'
                      : '—',
                  key: const Key('total-available'),
                  style: const TextStyle(
                    fontSize: 65,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -3,
                    height: 1.15,
                    color: ParkingColors.green,
                  ),
                ),
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'spaces',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      'available',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              !snapshot.hasSamples && snapshot.capacity > 0
                  ? 'Waiting for valid recorded results.'
                  : !snapshot.isDemo
                  ? 'Spaces classified vacant in the selected recordings.'
                  : snapshot.capacity == 0
                  ? 'Availability will appear when areas are configured.'
                  : snapshot.available == 0
                  ? 'All spaces are currently occupied.'
                  : 'Your next stop has room for you.',
              style: const TextStyle(fontSize: 13, color: ParkingColors.muted),
            ),
            if (snapshot.unresolved > 0)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Text(
                  '${snapshot.unresolved} unresolved · not counted as available',
                  style: const TextStyle(
                    fontSize: 12,
                    color: ParkingColors.muted,
                  ),
                ),
              ),
            if (snapshot.provisionalOccupied > 0 ||
                snapshot.provisionalVacant > 0)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Text(
                  '${snapshot.provisionalOccupied} occupied (P) · ${snapshot.provisionalVacant} vacant (P)\nP = provisional model estimate, included in counts.',
                  style: const TextStyle(
                    fontSize: 12,
                    height: 1.6,
                    color: ParkingColors.muted,
                  ),
                ),
              ),
            const SizedBox(height: 25),
            FilledButton(
              onPressed: onViewAreas,
              child: const Wrap(
                alignment: WrapAlignment.center,
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 22,
                children: [
                  Text('View parking areas'),
                  Icon(Icons.arrow_downward_rounded, size: 17),
                ],
              ),
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 19,
              runSpacing: 10,
              children: [
                _SmallFact(
                  icon: Icons.location_on_outlined,
                  text: '${snapshot.areas.length} parking areas',
                ),
                _SmallFact(
                  icon: Icons.local_parking_rounded,
                  text: '${snapshot.capacity} total spaces',
                ),
              ],
            ),
          ],
        );
        final chart = Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            OccupancyRing(snapshot: snapshot, progress: progress),
            const SizedBox(height: 8),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 22,
              runSpacing: 10,
              children: [
                _Legend(
                  color: ParkingColors.blue,
                  label: 'Occupied',
                  value: snapshot.occupied,
                ),
                _Legend(
                  color: ParkingColors.mint,
                  label: 'Available',
                  value: snapshot.available,
                ),
                if (snapshot.unresolved > 0)
                  _Legend(
                    color: const Color(0xFFB9C3D1),
                    label: 'Unresolved',
                    value: snapshot.unresolved,
                  ),
              ],
            ),
          ],
        );
        if (!wide) {
          return Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                heading,
                const SizedBox(height: 16),
                Center(child: chart),
                const SizedBox(height: 20),
                const Divider(color: ParkingColors.border),
                const SizedBox(height: 20),
                information,
              ],
            ),
          );
        }
        return Stack(
          children: [
            Positioned(
              right: -95,
              top: -90,
              child: IgnorePointer(
                child: Container(
                  width: 360,
                  height: 360,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [Color(0xFFF0F5FF), Color(0x00F0F5FF)],
                    ),
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 38, vertical: 27),
              child: Row(
                children: [
                  Expanded(flex: 5, child: information),
                  Container(
                    width: 1,
                    height: 230,
                    margin: const EdgeInsets.symmetric(horizontal: 24),
                    color: ParkingColors.border,
                  ),
                  Expanded(flex: 5, child: chart),
                ],
              ),
            ),
          ],
        );
      },
    ),
  );
}

class _SmallFact extends StatelessWidget {
  const _SmallFact({required this.icon, required this.text});
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 14, color: ParkingColors.muted),
      const SizedBox(width: 5),
      Flexible(
        child: Text(
          text,
          style: const TextStyle(fontSize: 11, color: ParkingColors.muted),
        ),
      ),
    ],
  );
}

class _Legend extends StatelessWidget {
  const _Legend({
    required this.color,
    required this.label,
    required this.value,
  });
  final Color color;
  final String label;
  final int value;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
      const SizedBox(width: 7),
      Text(
        label,
        style: const TextStyle(fontSize: 11, color: ParkingColors.muted),
      ),
      const SizedBox(width: 6),
      Text(
        '$value',
        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800),
      ),
    ],
  );
}

class _Footer extends StatelessWidget {
  const _Footer({required this.isDemo});
  final bool isDemo;
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.only(top: 18),
    decoration: const BoxDecoration(
      border: Border(top: BorderSide(color: ParkingColors.border)),
    ),
    child: Wrap(
      alignment: WrapAlignment.spaceBetween,
      spacing: 30,
      runSpacing: 10,
      children: [
        Text(
          '♡  A little less searching. A better arrival.',
          style: TextStyle(fontSize: 11, color: ParkingColors.muted),
        ),
        Text(
          isDemo
              ? 'Demo preview · Live availability is not connected'
              : 'Recorded model estimates · Not live availability',
          style: TextStyle(fontSize: 11, color: ParkingColors.muted),
        ),
      ],
    ),
  );
}
