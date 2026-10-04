import 'package:flutter/material.dart';
import 'data/parking_snapshot.dart';
import 'home_page.dart';
import 'theme.dart';
import 'backend_home.dart';
import 'data/parking_api.dart';
import 'replay_page.dart';

void main() => runApp(const ParkingApp());

class ParkingApp extends StatelessWidget {
  const ParkingApp({super.key, this.snapshot, this.api});

  final ParkingSnapshot? snapshot;
  final ParkingApi? api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Parking — Find your next space',
      debugShowCheckedModeBanner: false,
      theme: parkingTheme,
      routes: {'/replay': (_) => const ReplayPage()},
      home: snapshot == null
          ? BackendHome(api: api)
          : ParkingHomePage(snapshot: snapshot!),
    );
  }
}
