import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../app_theme.dart';
import '../models/gids_state.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<GidsState>();
    return Scaffold(
      backgroundColor: kBg,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          children: [
            _Header(state: state),
            const SizedBox(height: 20),
            _StatusHero(state: state),
            const SizedBox(height: 16),
            _MetricsRow(state: state),
            if (state.updateNeeded) ...[
              const SizedBox(height: 16),
              _UpdateBanner(version: state.updateVersion),
            ],
            if (state.attacks.isNotEmpty) ...[
              const SizedBox(height: 24),
              _RecentActivity(attacks: state.attacks.take(3).toList()),
            ],
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Header
// ─────────────────────────────────────────────

class _Header extends StatelessWidget {
  final GidsState state;
  const _Header({required this.state});

  @override
  Widget build(BuildContext context) {
    final live = state.connected;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('GIDS', style: TextStyle(
              color: kGold,
              fontSize: 10,
              letterSpacing: 4,
              fontWeight: FontWeight.w700,
            )),
            const Text('MONITOR', style: TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.w700,
              letterSpacing: 2,
              height: 1.1,
            )),
          ],
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: (live ? kSafe : kDanger).withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: (live ? kSafe : kDanger).withValues(alpha: 0.3),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6, height: 6,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: live ? kSafe : kDanger,
                  boxShadow: [BoxShadow(
                    color: (live ? kSafe : kDanger).withValues(alpha: 0.7),
                    blurRadius: 6,
                  )],
                ),
              ),
              const SizedBox(width: 7),
              Text(
                live ? 'LIVE' : 'OFFLINE',
                style: TextStyle(
                  color: live ? kSafe : kDanger,
                  fontSize: 10,
                  letterSpacing: 2,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────
// Status hero
// ─────────────────────────────────────────────

class _StatusHero extends StatelessWidget {
  final GidsState state;
  const _StatusHero({required this.state});

  @override
  Widget build(BuildContext context) {
    final attack = state.underAttack;
    final accent = attack ? kDanger : kSafe;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 44, horizontal: 24),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: attack
              ? [const Color(0xFF2A0606), const Color(0xFF0E0101)]
              : [const Color(0xFF062018), const Color(0xFF010D09)],
        ),
        border: Border.all(
          color: accent.withValues(alpha: 0.25),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: accent.withValues(alpha: 0.12),
            blurRadius: 40,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            width: 88,
            height: 88,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: accent.withValues(alpha: 0.08),
              boxShadow: [
                BoxShadow(
                  color: accent.withValues(alpha: 0.4),
                  blurRadius: 36,
                  spreadRadius: 6,
                ),
              ],
            ),
            child: Icon(
              attack ? Icons.gpp_bad_rounded : Icons.verified_user_rounded,
              size: 44,
              color: accent,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            attack ? 'THREAT DETECTED' : 'SYSTEM SECURED',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w800,
              letterSpacing: 4,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            attack
                ? 'CAN bus intrusion in progress'
                : 'All vehicle channels nominal',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.35),
              fontSize: 13,
              letterSpacing: 0.5,
            ),
          ),
          if (state.lastUpdate != null) ...[
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.04),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: Colors.white.withValues(alpha: 0.06),
                ),
              ),
              child: Text(
                'Updated ${DateFormat('HH:mm:ss').format(state.lastUpdate!)}',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.3),
                  fontSize: 11,
                  letterSpacing: 1,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Metrics row
// ─────────────────────────────────────────────

class _MetricsRow extends StatelessWidget {
  final GidsState state;
  const _MetricsRow({required this.state});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: _MetricCard(
          label: 'ROUND',
          value: '${state.round}',
          icon: Icons.loop_rounded,
        )),
        const SizedBox(width: 10),
        Expanded(child: _MetricCard(
          label: 'ACCURACY',
          value: '${state.accuracy.toStringAsFixed(1)}%',
          icon: Icons.bar_chart_rounded,
        )),
        const SizedBox(width: 10),
        Expanded(child: _MetricCard(
          label: 'D1 LOSS',
          value: state.loss.toStringAsFixed(3),
          icon: Icons.show_chart_rounded,
        )),
      ],
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  const _MetricCard({required this.label, required this.value, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 10),
      decoration: BoxDecoration(
        color: kSurface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kBorder, width: 1),
      ),
      child: Column(
        children: [
          Icon(icon, color: kGold.withValues(alpha: 0.7), size: 16),
          const SizedBox(height: 10),
          Text(value, style: const TextStyle(
            color: Colors.white,
            fontSize: 17,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          )),
          const SizedBox(height: 5),
          Text(label, style: kLabelStyle),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Update banner
// ─────────────────────────────────────────────

class _UpdateBanner extends StatelessWidget {
  final String version;
  const _UpdateBanner({required this.version});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            const Color(0xFF1A1200),
            const Color(0xFF0D0900),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kGold.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(Icons.system_update_alt_rounded, color: kGold, size: 22),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('UPDATE AVAILABLE', style: TextStyle(
                  color: kGold,
                  fontSize: 11,
                  letterSpacing: 2,
                  fontWeight: FontWeight.w700,
                )),
                const SizedBox(height: 2),
                Text(
                  version.isNotEmpty ? 'Version $version' : 'Connect to Wi-Fi to update',
                  style: TextStyle(color: Colors.white.withValues(alpha: 0.4), fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Recent activity
// ─────────────────────────────────────────────

class _RecentActivity extends StatelessWidget {
  final List<AttackEvent> attacks;
  const _RecentActivity({required this.attacks});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(width: 3, height: 14,
              decoration: BoxDecoration(
                color: kGold,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 10),
            const Text('RECENT ACTIVITY', style: TextStyle(
              color: Colors.white,
              fontSize: 11,
              letterSpacing: 3,
              fontWeight: FontWeight.w600,
            )),
          ],
        ),
        const SizedBox(height: 12),
        ...attacks.map((a) => _RecentTile(attack: a)),
      ],
    );
  }
}

class _RecentTile extends StatelessWidget {
  final AttackEvent attack;
  const _RecentTile({required this.attack});

  @override
  Widget build(BuildContext context) {
    final color = attack.attackPct > 50 ? kDanger : kWarn;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
      decoration: BoxDecoration(
        color: kSurface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kBorder),
      ),
      child: Row(
        children: [
          Container(
            width: 36, height: 36,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(Icons.warning_amber_rounded, color: color, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${attack.dataset} Attack', style: const TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                )),
                const SizedBox(height: 2),
                Text(
                  'Client ${attack.clientId}  •  ${attack.attackPct.toStringAsFixed(1)}%  •  ${DateFormat('HH:mm').format(attack.timestamp)}',
                  style: TextStyle(color: kSub, fontSize: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
