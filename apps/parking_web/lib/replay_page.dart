import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'theme.dart';

Map<String, dynamic> validateReplaySnapshot(Map<String, dynamic> data) {
  if (data['mode'] != 'replay' ||
      data['live_availability'] != false ||
      data['simulation'] != true ||
      data['bays'] is! List) {
    throw const FormatException('Unexpected replay response');
  }
  final bays = (data['bays'] as List).cast<Map<String, dynamic>>();
  final counts = <String, int>{
    'occupied': 0,
    'vacant': 0,
    'unknown': 0,
    'stale': 0,
  };
  var available = 0;
  var provisionalOccupied = 0;
  final ids = <String>{};
  for (final bay in bays) {
    final state = bay['state'];
    final id = bay['bay_id'];
    if (!counts.containsKey(state) || id is! String || !ids.add(id)) {
      throw const FormatException('Invalid replay bay');
    }
    counts[state] = counts[state]! + 1;
    if (bay['available'] == true) {
      if (state != 'vacant' || bay['fresh'] != true) {
        throw const FormatException('Unavailable bay advertised as free');
      }
      available++;
    }
    if (state == 'occupied' && bay['provisional'] == true) {
      provisionalOccupied++;
    }
  }
  final serverCounts = data['counts'];
  if (data['capacity'] != bays.length ||
      data['available'] != available ||
      data['provisional_occupied'] != provisionalOccupied ||
      serverCounts is! Map ||
      counts.keys.any((key) => serverCounts[key] != counts[key])) {
    throw const FormatException('Inconsistent replay totals');
  }
  return data;
}

/// Historical frames arrive at a three-second cadence. This screen never
/// advertises current availability, even if a bay was vacant in the recording.
class ReplayPage extends StatefulWidget {
  const ReplayPage({super.key, this.client, this.base});
  final http.Client? client;
  final Uri? base;

  @override
  State<ReplayPage> createState() => _ReplayPageState();
}

class _ReplayPageState extends State<ReplayPage> {
  late final http.Client _client;
  late final bool _ownsClient;
  late final Uri _base;
  Timer? _timer;
  Map<String, dynamic>? _data;
  String _selected = 'chad-1';
  String? _error;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _ownsClient = widget.client == null;
    _client = widget.client ?? http.Client();
    _base = widget.base ?? Uri.base;
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 3), (_) => _refresh());
  }

  Future<void> _refresh() async {
    if (_busy) return;
    try {
      final response = await _client
          .get(_base.resolve('/api/replay'))
          .timeout(const Duration(seconds: 8));
      if (response.statusCode != 200) {
        throw StateError('Replay API unavailable');
      }
      final data = validateReplaySnapshot(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
      if (mounted) {
        setState(() {
          _data = data;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _data = null;
          _error = 'Replay backend unavailable. Historical counts are hidden.';
        });
      }
    }
  }

  Future<void> _post(String path, [Map<String, dynamic>? body]) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final response = await _client
          .post(
            _base.resolve(path),
            headers: {
              'X-Parking-Client': 'web',
              'Content-Type': 'application/json',
            },
            body: body == null ? null : jsonEncode(body),
          )
          .timeout(const Duration(seconds: 8));
      if (response.statusCode != 202) {
        throw StateError(
          response.statusCode == 409
              ? 'Another replay is still running. Stop it before starting a new one.'
              : 'Could not change the replay.',
        );
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error.toString().replaceFirst('Bad state: ', ''),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        await _refresh();
      }
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    if (_ownsClient) _client.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    final bays =
        (data?['bays'] as List?)?.cast<Map<String, dynamic>>() ??
        const <Map<String, dynamic>>[];
    final status = data?['status'] as String? ?? 'idle';
    final running =
        status == 'preparing' || status == 'playing' || status == 'stopping';
    final capacity = data?['capacity'] as int? ?? 0;
    final available = data?['available'] as int? ?? 0;
    final occupied = (data?['counts'] as Map?)?['occupied'] as int? ?? 0;
    final stale = (data?['counts'] as Map?)?['stale'] as int? ?? 0;
    final provisional = data?['provisional_occupied'] as int? ?? 0;
    return Scaffold(
      backgroundColor: ParkingColors.background,
      appBar: AppBar(
        title: const Text('Replay demo'),
        backgroundColor: ParkingColors.background,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1160),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 28,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Watch one recording unfold.',
                      style: Theme.of(context).textTheme.headlineMedium
                          ?.copyWith(
                            color: ParkingColors.navy,
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Simulation, not live availability. Frame times are positions in historical footage; the original capture time is unknown.',
                      style: TextStyle(color: ParkingColors.muted),
                    ),
                    const SizedBox(height: 20),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Wrap(
                              spacing: 12,
                              runSpacing: 12,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                SizedBox(
                                  width: 210,
                                  child: DropdownButtonFormField<String>(
                                    initialValue: _selected,
                                    isExpanded: true,
                                    decoration: const InputDecoration(
                                      labelText: 'Historical recording',
                                      border: OutlineInputBorder(),
                                    ),
                                    items: const [
                                      DropdownMenuItem(
                                        value: 'chad-1',
                                        child: Text('CHAD · Recording 1'),
                                      ),
                                      DropdownMenuItem(
                                        value: 'chad-2',
                                        child: Text('CHAD · Recording 2'),
                                      ),
                                      DropdownMenuItem(
                                        value: 'chad-3',
                                        child: Text('CHAD · Recording 3'),
                                      ),
                                      DropdownMenuItem(
                                        value: 'chad-4',
                                        child: Text('CHAD · Recording 4'),
                                      ),
                                      DropdownMenuItem(
                                        value: 'overhead-1',
                                        child: Text('Overhead · Recording 1'),
                                      ),
                                    ],
                                    onChanged: running
                                        ? null
                                        : (value) {
                                            if (value != null) {
                                              setState(() => _selected = value);
                                            }
                                          },
                                  ),
                                ),
                                FilledButton.icon(
                                  onPressed: running || _busy
                                      ? null
                                      : () => _post('/api/replay/start', {
                                          'source_id': _selected,
                                        }),
                                  icon: const Icon(Icons.play_arrow_rounded),
                                  label: const Text('Start paced replay'),
                                  style: FilledButton.styleFrom(
                                    minimumSize: const Size(48, 50),
                                  ),
                                ),
                                OutlinedButton.icon(
                                  onPressed: running && !_busy
                                      ? () => _post('/api/replay/stop')
                                      : null,
                                  icon: const Icon(Icons.stop_rounded),
                                  label: const Text('Stop'),
                                  style: OutlinedButton.styleFrom(
                                    minimumSize: const Size(48, 50),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            Text(
                              _error ??
                                  data?['message'] as String? ??
                                  'Connecting…',
                              style: TextStyle(
                                color: _error == null
                                    ? ParkingColors.muted
                                    : Colors.red.shade700,
                              ),
                            ),
                            if (data?['source_id'] != null) ...[
                              const SizedBox(height: 6),
                              Text(
                                '${data!['source_id']} · video position ${((data['replay_seconds'] as num?)?.toStringAsFixed(0) ?? '—')} s'
                                ' · processed ${data['last_processed_at'] ?? '—'}',
                                style: const TextStyle(
                                  color: ParkingColors.muted,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 22),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        _Metric(label: 'Mapped bays', value: '$capacity'),
                        _Metric(
                          label: 'Historically available',
                          value: '$available',
                        ),
                        _Metric(
                          label: 'Occupied estimates',
                          value: '$occupied',
                        ),
                        _Metric(
                          label: 'Provisional occupied',
                          value: '$provisional',
                        ),
                        _Metric(label: 'Stale / unavailable', value: '$stale'),
                      ],
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'Individual bays',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: ParkingColors.navy,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'A possible occupied result blocks availability immediately. A state change confirms after three valid observations.',
                      style: TextStyle(color: ParkingColors.muted),
                    ),
                    const SizedBox(height: 12),
                    if (bays.isEmpty)
                      const Text('Start a replay to see bay observations.'),
                    LayoutBuilder(
                      builder: (context, constraints) {
                        final width = constraints.maxWidth;
                        final columns = width >= 900
                            ? 4
                            : width >= 600
                            ? 3
                            : width >= 390
                            ? 2
                            : 1;
                        return GridView.builder(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: bays.length,
                          gridDelegate:
                              SliverGridDelegateWithFixedCrossAxisCount(
                                crossAxisCount: columns,
                                crossAxisSpacing: 12,
                                mainAxisSpacing: 12,
                                mainAxisExtent: 128,
                              ),
                          itemBuilder: (context, index) =>
                              _BayCard(bay: bays[index]),
                        );
                      },
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
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});
  final String label, value;
  @override
  Widget build(BuildContext context) => Container(
    constraints: const BoxConstraints(minWidth: 145),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: const TextStyle(
            fontSize: 26,
            fontWeight: FontWeight.w800,
            color: ParkingColors.navy,
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: ParkingColors.muted),
        ),
      ],
    ),
  );
}

class _BayCard extends StatelessWidget {
  const _BayCard({required this.bay});
  final Map<String, dynamic> bay;
  @override
  Widget build(BuildContext context) {
    final state = bay['state'] as String? ?? 'unknown';
    final provisional = bay['provisional'] == true;
    final label = state == 'occupied' && provisional
        ? 'OCCUPIED (P)'
        : state.toUpperCase();
    final confirmed = bay['confirmed_state'] as String?;
    final detail = state == 'stale'
        ? 'Last confirmed ${confirmed ?? 'none'}'
        : confirmed == state
        ? 'Confirmed · ${bay['source'] ?? 'no source'}'
        : 'Candidate ${bay['candidate_streak'] ?? 0}/3 · ${bay['source'] ?? 'no source'}';
    final color = state == 'vacant'
        ? const Color(0xFF087E66)
        : state == 'occupied'
        ? const Color(0xFFAB4F3B)
        : ParkingColors.muted;
    return Semantics(
      label:
          '${bay['bay_id']}, $label, source ${bay['source'] ?? 'unresolved'}, '
          'candidate ${bay['candidate_state'] ?? 'none'}, confirmed ${bay['confirmed_state'] ?? 'none'}',
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withValues(alpha: .25)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              bay['bay_id'] as String? ?? 'Bay',
              style: const TextStyle(
                fontWeight: FontWeight.w800,
                color: ParkingColors.navy,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w800,
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              detail,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11, color: ParkingColors.muted),
            ),
          ],
        ),
      ),
    );
  }
}
