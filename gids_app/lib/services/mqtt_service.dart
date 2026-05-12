import 'dart:convert';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';
import '../models/gids_state.dart';

class MqttService {
  final GidsState state;
  String host;
  int port;

  late MqttServerClient _client;
  bool _started = false;

  MqttService({required this.state, required this.host, required this.port});

  Future<void> start() async {
    if (_started) return;
    _started = true;

    _client = MqttServerClient.withPort(host, 'gids_app_${DateTime.now().millisecondsSinceEpoch}', port);
    _client.keepAlivePeriod      = 30;
    _client.connectTimeoutPeriod = 5000;
    _client.autoReconnect        = true;
    _client.onConnected          = _onConnected;
    _client.onDisconnected       = _onDisconnected;
    _client.onAutoReconnected    = _onConnected;
    _client.logging(on: false);
    _client.setProtocolV311();

    final connMsg = MqttConnectMessage()
        .withClientIdentifier('gids_app')
        .startClean();
    _client.connectionMessage = connMsg;

    try {
      await _client.connect();
    } catch (_) {
      state.setConnected(false);
      return;
    }

    if (_client.connectionStatus?.state == MqttConnectionState.connected) {
      _subscribe('gids/status');
      _subscribe('gids/attack');
      _subscribe('gids/update_needed');

      _client.updates?.listen(_onMessage);
    }
  }

  void _subscribe(String topic) {
    _client.subscribe(topic, MqttQos.atLeastOnce);
  }

  void _onConnected() => state.setConnected(true);
  void _onDisconnected() => state.setConnected(false);

  void _onMessage(List<MqttReceivedMessage<MqttMessage?>>? messages) {
    if (messages == null) return;
    for (final msg in messages) {
      final pub = msg.payload as MqttPublishMessage;
      final raw = MqttPublishPayload.bytesToStringAsString(pub.payload.message);
      try {
        final data = jsonDecode(raw) as Map<String, dynamic>;
        final type = data['type'] as String? ?? '';
        switch (type) {
          case 'status':
            state.onRoundStatus(
              (data['round']    as num).toInt(),
              (data['loss']     as num).toDouble(),
              (data['accuracy'] as num).toDouble(),
            );
          case 'attack':
            state.onAttack(
              (data['client_id']  as num).toInt(),
              data['dataset']     as String? ?? '',
              (data['attack_pct'] as num).toDouble() / 100.0,
              (data['round']      as num? ?? 0).toInt(),
            );
          case 'update_needed':
            state.onUpdateNeeded(data['version'] as String? ?? '');
        }
      } catch (_) {}
    }
  }

  Future<void> restart(String newHost, int newPort) async {
    dispose();
    host = newHost;
    port = newPort;
    _started = false;
    start(); // fire-and-forget; _onConnected/_onDisconnected update UI
  }

  void dispose() {
    if (_started) _client.disconnect();
    _started = false;
  }
}
