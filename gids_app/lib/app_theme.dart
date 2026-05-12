import 'package:flutter/material.dart';

const kGold    = Color(0xFFC9A84C);
const kBg      = Color(0xFF090909);
const kSurface = Color(0xFF131313);
const kBorder  = Color(0xFF242424);
const kSafe    = Color(0xFF00C896);
const kDanger  = Color(0xFFFF4444);
const kWarn    = Color(0xFFFF8C42);
const kSub     = Color(0xFF666666);

BoxDecoration glassCard({Color? borderColor, List<BoxShadow>? shadows}) =>
    BoxDecoration(
      color: kSurface,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: borderColor ?? kBorder, width: 1),
      boxShadow: shadows,
    );

TextStyle get kLabelStyle => const TextStyle(
  color: kSub,
  fontSize: 9,
  letterSpacing: 2,
  fontWeight: FontWeight.w600,
);
