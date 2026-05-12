import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../app_theme.dart';
import '../models/gids_state.dart';

class AttackLogScreen extends StatelessWidget {
  const AttackLogScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final attacks = context.watch<GidsState>().attacks;

    return Scaffold(
      backgroundColor: kBg,
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _LogHeader(count: attacks.length),
            Expanded(
              child: attacks.isEmpty
                  ? const _EmptyState()
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                      itemCount: attacks.length,
                      itemBuilder: (_, i) => _AttackTile(attack: attacks[i]),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Header
// ─────────────────────────────────────────────

class _LogHeader extends StatelessWidget {
  final int count;
  const _LogHeader({required this.count});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
      child: Row(
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
              const Text('ATTACK LOG', style: TextStyle(
                color: Colors.white,
                fontSize: 26,
                fontWeight: FontWeight.w700,
                letterSpacing: 2,
                height: 1.1,
              )),
            ],
          ),
          if (count > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: kDanger.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: kDanger.withValues(alpha: 0.3)),
              ),
              child: Text(
                '$count EVENT${count == 1 ? '' : 'S'}',
                style: const TextStyle(
                  color: kDanger,
                  fontSize: 10,
                  letterSpacing: 2,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Empty state
// ─────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80, height: 80,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: kSafe.withValues(alpha: 0.08),
              boxShadow: [BoxShadow(
                color: kSafe.withValues(alpha: 0.3),
                blurRadius: 30,
                spreadRadius: 4,
              )],
            ),
            child: const Icon(Icons.verified_user_rounded, size: 38, color: kSafe),
          ),
          const SizedBox(height: 20),
          const Text('NO ATTACKS DETECTED', style: TextStyle(
            color: Colors.white,
            fontSize: 14,
            letterSpacing: 3,
            fontWeight: FontWeight.w700,
          )),
          const SizedBox(height: 8),
          Text('All channels secure', style: TextStyle(
            color: Colors.white.withValues(alpha: 0.3),
            fontSize: 13,
          )),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Attack tile
// ─────────────────────────────────────────────

class _AttackTile extends StatelessWidget {
  final AttackEvent attack;
  const _AttackTile({required this.attack});

  @override
  Widget build(BuildContext context) {
    final high   = attack.attackPct > 50;
    final color  = high ? kDanger : kWarn;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: kSurface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kBorder),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: IntrinsicHeight(
          child: Row(
            children: [
              Container(width: 3, color: color),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                  child: Row(
                    children: [
                      Container(
                        width: 40, height: 40,
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Center(
                          child: Text('C${attack.clientId}', style: TextStyle(
                            color: color,
                            fontSize: 12,
                            fontWeight: FontWeight.w800,
                          )),
                        ),
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
                            const SizedBox(height: 4),
                            Text(
                              'Round ${attack.round}  •  ${DateFormat('HH:mm:ss').format(attack.timestamp)}',
                              style: TextStyle(color: kSub, fontSize: 11),
                            ),
                          ],
                        ),
                      ),
                      Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            '${attack.attackPct.toStringAsFixed(1)}%',
                            style: TextStyle(
                              color: color,
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          Text('flagged', style: TextStyle(
                            color: kSub,
                            fontSize: 9,
                            letterSpacing: 1,
                          )),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
