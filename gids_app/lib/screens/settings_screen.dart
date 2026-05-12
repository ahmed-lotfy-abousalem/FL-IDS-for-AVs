import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../app_theme.dart';
import '../services/mqtt_service.dart';

class SettingsScreen extends StatefulWidget {
  final MqttService mqttService;
  const SettingsScreen({super.key, required this.mqttService});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _hostCtrl;
  late final TextEditingController _portCtrl;

  @override
  void initState() {
    super.initState();
    _hostCtrl = TextEditingController(text: widget.mqttService.host);
    _portCtrl = TextEditingController(text: '${widget.mqttService.port}');
  }

  @override
  void dispose() {
    _hostCtrl.dispose();
    _portCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBg,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 40),
          children: [
            // Header
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('GIDS', style: TextStyle(
                  color: kGold,
                  fontSize: 10,
                  letterSpacing: 4,
                  fontWeight: FontWeight.w700,
                )),
                const Text('SETTINGS', style: TextStyle(
                  color: Colors.white,
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 2,
                  height: 1.1,
                )),
              ],
            ),
            const SizedBox(height: 32),

            // Broker section
            _SectionLabel(label: 'MQTT BROKER'),
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: kSurface,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: kBorder),
              ),
              child: Column(
                children: [
                  TextField(
                    controller: _hostCtrl,
                    style: const TextStyle(color: Colors.white, fontSize: 14),
                    decoration: const InputDecoration(
                      labelText: 'Broker IP / Host',
                      prefixIcon: Icon(Icons.router_outlined, color: kSub, size: 18),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _portCtrl,
                    style: const TextStyle(color: Colors.white, fontSize: 14),
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    decoration: const InputDecoration(
                      labelText: 'Port',
                      prefixIcon: Icon(Icons.settings_ethernet_outlined, color: kSub, size: 18),
                    ),
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFFC9A84C), Color(0xFFE4C97A)],
                        ),
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: [BoxShadow(
                          color: kGold.withValues(alpha: 0.3),
                          blurRadius: 16,
                          offset: const Offset(0, 4),
                        )],
                      ),
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.transparent,
                          shadowColor: Colors.transparent,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        icon: const Icon(Icons.refresh_rounded,
                            color: Colors.black, size: 18),
                        label: const Text('RECONNECT', style: TextStyle(
                          color: Colors.black,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 2,
                          fontSize: 13,
                        )),
                        onPressed: () async {
                          final host = _hostCtrl.text.trim();
                          final port = int.tryParse(_portCtrl.text) ?? 1883;
                          final prefs = await SharedPreferences.getInstance();
                          await prefs.setString('mqtt_host', host);
                          await prefs.setInt('mqtt_port', port);
                          widget.mqttService.restart(host, port);
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Connecting to $host:$port…'),
                                backgroundColor: kSurface,
                                behavior: SnackBarBehavior.floating,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(10),
                                ),
                              ),
                            );
                          }
                        },
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 28),

            // Topics section
            _SectionLabel(label: 'SUBSCRIBED TOPICS'),
            const SizedBox(height: 14),
            Container(
              decoration: BoxDecoration(
                color: kSurface,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: kBorder),
              ),
              child: Column(
                children: const [
                  _TopicTile(
                    topic: 'gids/status',
                    desc: 'Round accuracy & loss',
                    icon: Icons.bar_chart_rounded,
                    first: true,
                  ),
                  _TopicTile(
                    topic: 'gids/attack',
                    desc: 'Attack events from clients',
                    icon: Icons.emergency_rounded,
                  ),
                  _TopicTile(
                    topic: 'gids/update_needed',
                    desc: 'New federated model ready',
                    icon: Icons.system_update_alt_rounded,
                    last: true,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String label;
  const _SectionLabel({required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 3, height: 12,
          decoration: BoxDecoration(
            color: kGold,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 8),
        Text(label, style: const TextStyle(
          color: kSub,
          fontSize: 10,
          letterSpacing: 2.5,
          fontWeight: FontWeight.w600,
        )),
      ],
    );
  }
}

class _TopicTile extends StatelessWidget {
  final String topic;
  final String desc;
  final IconData icon;
  final bool first;
  final bool last;
  const _TopicTile({
    required this.topic,
    required this.desc,
    required this.icon,
    this.first = false,
    this.last = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        if (!first)
          Divider(height: 1, color: kBorder, indent: 16, endIndent: 16),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Container(
                width: 36, height: 36,
                decoration: BoxDecoration(
                  color: kGold.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: kGold, size: 16),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(topic, style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.w500,
                    )),
                    const SizedBox(height: 2),
                    Text(desc, style: TextStyle(color: kSub, fontSize: 11)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
