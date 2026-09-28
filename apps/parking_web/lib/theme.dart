import 'package:flutter/material.dart';

abstract final class ParkingColors {
  static const background = Color(0xFFF7F9FC);
  static const navy = Color(0xFF172B4D);
  static const muted = Color(0xFF617089);
  static const blue = Color(0xFF315FEA);
  static const paleBlue = Color(0xFFEEF3FF);
  static const green = Color(0xFF13785B);
  static const mint = Color(0xFFB8EBD9);
  static const paleMint = Color(0xFFE8F7F0);
  static const border = Color(0xFFE5EBF3);
}

final parkingTheme = ThemeData(
  useMaterial3: true,
  fontFamily: 'Manrope',
  scaffoldBackgroundColor: ParkingColors.background,
  colorScheme: ColorScheme.fromSeed(
    seedColor: ParkingColors.blue,
    primary: ParkingColors.blue,
    onPrimary: Colors.white,
    surface: Colors.white,
    onSurface: ParkingColors.navy,
  ),
  textTheme: const TextTheme(
    bodyMedium: TextStyle(fontSize: 14, height: 1.6, color: ParkingColors.navy),
    bodySmall: TextStyle(fontSize: 12, height: 1.5, color: ParkingColors.muted),
  ),
  filledButtonTheme: FilledButtonThemeData(
    style: FilledButton.styleFrom(
      minimumSize: const Size(48, 52),
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      textStyle: const TextStyle(
        fontFamily: 'Manrope',
        fontWeight: FontWeight.w700,
        fontSize: 14,
      ),
    ),
  ),
  textButtonTheme: TextButtonThemeData(
    style: TextButton.styleFrom(
      minimumSize: const Size(48, 48),
      textStyle: const TextStyle(
        fontFamily: 'Manrope',
        fontWeight: FontWeight.w700,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
  ),
);
