import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'app_theme.dart';
import 'models/gids_state.dart';
import 'services/mqtt_service.dart';
import 'screens/dashboard_screen.dart';
import 'screens/attack_log_screen.dart';
import 'screens/settings_screen.dart';

const _kDefaultHost = '192.168.1.23';
const _kDefaultPort = 1883;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));
  final prefs = await SharedPreferences.getInstance();
  final host = prefs.getString('mqtt_host') ?? _kDefaultHost;
  final port = prefs.getInt('mqtt_port')   ?? _kDefaultPort;
  runApp(GidsApp(brokerHost: host, brokerPort: port));
}

class GidsApp extends StatefulWidget {
  final String brokerHost;
  final int brokerPort;
  const GidsApp({super.key, required this.brokerHost, required this.brokerPort});

  @override
  State<GidsApp> createState() => _GidsAppState();
}

class _GidsAppState extends State<GidsApp> {
  final _state = GidsState();
  late final MqttService _mqtt;

  @override
  void initState() {
    super.initState();
    _mqtt = MqttService(state: _state, host: widget.brokerHost, port: widget.brokerPort);
    _mqtt.start();
  }

  @override
  void dispose() {
    _mqtt.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: _state,
      child: MaterialApp(
        title: 'GIDS Monitor',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          brightness: Brightness.dark,
          scaffoldBackgroundColor: kBg,
          colorScheme: const ColorScheme.dark(
            primary: kGold,
            surface: kSurface,
            onSurface: Colors.white,
          ),
          useMaterial3: true,
          navigationBarTheme: NavigationBarThemeData(
            backgroundColor: const Color(0xFF0D0D0D),
            elevation: 0,
            height: 64,
            indicatorColor: kGold.withValues(alpha: 0.15),
            labelTextStyle: WidgetStateProperty.resolveWith((states) {
              final selected = states.contains(WidgetState.selected);
              return TextStyle(
                color: selected ? kGold : kSub,
                fontSize: 10,
                letterSpacing: 1.2,
                fontWeight: FontWeight.w600,
              );
            }),
            iconTheme: WidgetStateProperty.resolveWith((states) {
              final selected = states.contains(WidgetState.selected);
              return IconThemeData(
                color: selected ? kGold : kSub,
                size: 22,
              );
            }),
          ),
          dividerColor: kBorder,
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: kSurface,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: kBorder),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: kBorder),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: kGold, width: 1.5),
            ),
            labelStyle: const TextStyle(color: kSub),
          ),
        ),
        home: _HomeShell(mqttService: _mqtt),
      ),
    );
  }
}

class _HomeShell extends StatefulWidget {
  final MqttService mqttService;
  const _HomeShell({required this.mqttService});

  @override
  State<_HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<_HomeShell> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final screens = [
      const DashboardScreen(),
      const AttackLogScreen(),
      SettingsScreen(mqttService: widget.mqttService),
    ];

    return Scaffold(
      backgroundColor: kBg,
      body: screens[_tab],
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Color(0xFF0D0D0D),
          border: Border(top: BorderSide(color: kBorder, width: 0.5)),
        ),
        child: NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (i) => setState(() => _tab = i),
          backgroundColor: Colors.transparent,
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.shield_outlined),
              selectedIcon: Icon(Icons.shield_rounded),
              label: 'MONITOR',
            ),
            NavigationDestination(
              icon: Icon(Icons.emergency_outlined),
              selectedIcon: Icon(Icons.emergency_rounded),
              label: 'ATTACKS',
            ),
            NavigationDestination(
              icon: Icon(Icons.tune_outlined),
              selectedIcon: Icon(Icons.tune_rounded),
              label: 'SETTINGS',
            ),
          ],
        ),
      ),
    );
  }
}
