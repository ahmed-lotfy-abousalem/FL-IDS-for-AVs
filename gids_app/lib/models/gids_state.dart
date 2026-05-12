import 'package:flutter/foundation.dart';

class AttackEvent {
  final DateTime timestamp;
  final int clientId;
  final String dataset;
  final double attackPct;
  final int round;

  AttackEvent({
    required this.timestamp,
    required this.clientId,
    required this.dataset,
    required this.attackPct,
    required this.round,
  });
}

class GidsState extends ChangeNotifier {
  // Connection
  bool _connected = false;
  bool get connected => _connected;

  // Latest round status
  int _round = 0;
  double _accuracy = 0.0;
  double _loss = 0.0;
  DateTime? _lastUpdate;

  int    get round      => _round;
  double get accuracy   => _accuracy;
  double get loss       => _loss;
  DateTime? get lastUpdate => _lastUpdate;

  // Attack log (newest first)
  final List<AttackEvent> _attacks = [];
  List<AttackEvent> get attacks => List.unmodifiable(_attacks);

  // Update notification flag
  bool _updateNeeded = false;
  String _updateVersion = '';
  bool   get updateNeeded   => _updateNeeded;
  String get updateVersion  => _updateVersion;

  void setConnected(bool value) {
    _connected = value;
    notifyListeners();
  }

  void onRoundStatus(int round, double loss, double accuracy) {
    _round      = round;
    _loss       = loss;
    _accuracy   = accuracy;
    _lastUpdate = DateTime.now();
    notifyListeners();
  }

  void onAttack(int clientId, String dataset, double attackPct, int round) {
    _attacks.insert(0, AttackEvent(
      timestamp: DateTime.now(),
      clientId:  clientId,
      dataset:   dataset,
      attackPct: attackPct,
      round:     round,
    ));
    notifyListeners();
  }

  void onUpdateNeeded(String version) {
    _updateNeeded  = true;
    _updateVersion = version;
    notifyListeners();
  }

  bool get underAttack =>
      _attacks.isNotEmpty &&
      DateTime.now().difference(_attacks.first.timestamp).inMinutes < 5;
}
