import 'package:flutter/material.dart';
import 'data/parking_api.dart';
import 'data/parking_snapshot.dart';
import 'home_page.dart';
import 'theme.dart';

class BackendHome extends StatefulWidget {
  const BackendHome({super.key, this.api});
  final ParkingApi? api;
  @override
  State<BackendHome> createState() => _BackendHomeState();
}

class _BackendHomeState extends State<BackendHome> {
  late final ParkingController controller;
  @override
  void initState() {
    super.initState();
    controller = ParkingController(widget.api ?? ParkingApi())..start();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller,
    builder: (context, _) {
      final snapshot = controller.snapshot;
      final running =
          controller.submitting || snapshot?.analysisStatus == 'running';
      return ParkingHomePage(
        snapshot: snapshot ?? unavailableSnapshot,
        connectionPanel: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: ParkingColors.paleBlue,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Recorded camera results',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  color: ParkingColors.navy,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                controller.error ??
                    (snapshot == null
                        ? 'Connecting to the parking backend…'
                        : 'Actual model estimates from separate recordings. These totals are not live availability.'),
                style: const TextStyle(fontSize: 12, color: ParkingColors.navy),
              ),
              if (snapshot != null) ...[
                const SizedBox(height: 5),
                Text(
                  snapshot.analysisMessage,
                  style: const TextStyle(
                    fontSize: 12,
                    color: ParkingColors.muted,
                  ),
                ),
              ],
              if (controller.actionError != null)
                Text(
                  controller.actionError!,
                  style: const TextStyle(color: Colors.red),
                ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 16,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: 218,
                    child: DropdownButtonFormField<String>(
                      key: ValueKey(controller.selectedRecording),
                      initialValue: controller.selectedRecording,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'CHAD · Camera 1',
                        filled: true,
                        fillColor: Colors.white,
                        contentPadding: EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 12,
                        ),
                        border: OutlineInputBorder(borderSide: BorderSide.none),
                      ),
                      items: [
                        for (var i = 1; i <= 4; i++)
                          DropdownMenuItem(
                            value: 'chad-$i',
                            child: Text(
                              'Recording $i',
                              style: const TextStyle(fontSize: 13),
                            ),
                          ),
                      ],
                      onChanged: (value) {
                        if (value != null) controller.selectRecording(value);
                      },
                    ),
                  ),
                  OutlinedButton(
                    onPressed: running ? null : controller.analyze,
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size(48, 50),
                    ),
                    child: Wrap(
                      alignment: WrapAlignment.center,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: 8,
                      children: [
                        Icon(
                          running
                              ? Icons.hourglass_top_rounded
                              : Icons.refresh_rounded,
                          size: 17,
                        ),
                        Text(
                          running
                              ? 'Analyzing recordings…'
                              : 'Run new analysis',
                        ),
                      ],
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => Navigator.of(context).pushNamed('/replay'),
                    icon: const Icon(Icons.play_circle_outline_rounded),
                    label: const Text('Open replay demo'),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size(48, 50),
                    ),
                  ),
                  if (controller.error != null)
                    TextButton(
                      onPressed: controller.refresh,
                      child: const Text('Retry connection'),
                    ),
                ],
              ),
            ],
          ),
        ),
      );
    },
  );
}
