import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/mic_button.dart';
import '../account/account_data.dart';

/// One message in the chat.
class _Message {
  const _Message(this.role, this.text, {this.actions = const []});

  final String role;   // user or assistant
  final String text;
  final List<Map<String, dynamic>> actions;   // changes the assistant prepared, for the client to confirm
}

/// Ask about your bookings in your own words and language. The assistant can look and prepare changes,
/// but only the client's tap on Confirm actually moves or cancels anything.
class AssistantScreen extends ConsumerStatefulWidget {
  const AssistantScreen({super.key});

  @override
  ConsumerState<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends ConsumerState<AssistantScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_Message> _messages = [];
  bool _busy = false;

  static const _starters = [
    'What bookings do I have coming up?',
    'Can I move my next booking to later the same day?',
    'How much would it cost to cancel my next booking?',
  ];

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send([String? preset]) async {
    final text = (preset ?? _input.text).trim();
    if (text.isEmpty || _busy) return;
    setState(() {
      _messages.add(_Message('user', text));
      _input.clear();
      _busy = true;
    });
    _toBottom();
    try {
      final history = [
        for (final m in _messages.length > 20 ? _messages.sublist(_messages.length - 20) : _messages)
          {'role': m.role, 'content': m.text},
      ];
      final json = await ref.read(apiClientProvider).post('/api/client/assistant', body: {'messages': history});
      final reply = Map<String, dynamic>.from(json as Map);
      setState(() => _messages.add(_Message(
            'assistant',
            '${reply['reply'] ?? ''}',
            actions: [for (final a in (reply['actions'] as List? ?? const [])) Map<String, dynamic>.from(a as Map)],
          )));
    } on ApiException catch (problem) {
      setState(() => _messages.add(_Message('assistant', problem.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
      _toBottom();
    }
  }

  void _toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) {
          _scroll.animateTo(_scroll.position.maxScrollExtent, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
        }
      });

  Future<void> _confirm(Map<String, dynamic> action) async {
    final api = ref.read(accountApiProvider);
    final id = '${action['booking_id']}';
    try {
      if (action['type'] == 'reschedule') {
        await api.move(id, '${action['starts_at']}');
      } else {
        await api.cancel(id);
      }
      ref.invalidate(myBookingsProvider);
      setState(() => _messages.add(_Message('assistant',
          action['type'] == 'reschedule' ? 'Done. Your booking has been moved, and you’ll get a new confirmation.' : 'Done. Your booking is cancelled.')));
      _toBottom();
    } on ApiException catch (problem) {
      if (mounted) showMessage(context, problem.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ClientShell(
      child: Column(children: [
        Expanded(
          child: ListView(controller: _scroll, padding: const EdgeInsets.fromLTRB(20, 24, 20, 24), children: [
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Ask about your bookings', style: text.displaySmall),
                  const SizedBox(height: Space.sm),
                  Text('Type or speak in any language. I can look up your bookings and prepare changes, '
                      'but nothing changes until you tap Confirm.', style: text.bodyLarge?.copyWith(color: Palette.muted)),
                  const SizedBox(height: Space.xl),
                  if (_messages.isEmpty)
                    Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
                      for (final s in _starters) ActionChip(label: Text(s), onPressed: () => _send(s)),
                    ]),
                  for (final message in _messages) _Bubble(message: message, onConfirm: _confirm),
                  if (_busy)
                    const Padding(
                      padding: EdgeInsets.only(top: Space.md),
                      child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2)),
                    ),
                ]),
              ),
            ),
          ]),
        ),
        DecoratedBox(
          decoration: const BoxDecoration(color: Palette.surface, border: Border(top: BorderSide(color: Palette.line))),
          child: SafeArea(
            top: false,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
                  child: Row(children: [
                    Expanded(
                      child: TextField(
                        controller: _input,
                        minLines: 1,
                        maxLines: 4,
                        maxLength: 1000,
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _send(),
                        decoration: InputDecoration(
                          hintText: 'Message',
                          counterText: '',
                          suffixIcon: MicButton(context: 'assistant', onText: (words) => appendSpoken(_input, words)),
                        ),
                      ),
                    ),
                    const SizedBox(width: Space.sm),
                    IconButton.filled(
                      tooltip: 'Send',
                      onPressed: _busy ? null : _send,
                      icon: const Icon(Icons.arrow_upward_rounded),
                    ),
                  ]),
                ),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message, required this.onConfirm});

  final _Message message;
  final Future<void> Function(Map<String, dynamic> action) onConfirm;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final mine = message.role == 'user';
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: Space.md),
        constraints: const BoxConstraints(maxWidth: 560),
        child: Column(crossAxisAlignment: mine ? CrossAxisAlignment.end : CrossAxisAlignment.start, children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: mine ? Palette.forest : Palette.sage,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(16),
                topRight: const Radius.circular(16),
                bottomLeft: Radius.circular(mine ? 16 : 6),
                bottomRight: Radius.circular(mine ? 6 : 16),
              ),
            ),
            child: Text(message.text, style: text.bodyLarge?.copyWith(color: mine ? Colors.white : Palette.ink)),
          ),
          for (final action in message.actions) _ActionCard(action: action, onConfirm: onConfirm),
        ]),
      ),
    );
  }
}

class _ActionCard extends StatefulWidget {
  const _ActionCard({required this.action, required this.onConfirm});

  final Map<String, dynamic> action;
  final Future<void> Function(Map<String, dynamic> action) onConfirm;

  @override
  State<_ActionCard> createState() => _ActionCardState();
}

class _ActionCardState extends State<_ActionCard> {
  bool _done = false;
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final cancel = widget.action['type'] == 'cancel';
    return Container(
      margin: const EdgeInsets.only(top: Space.sm),
      child: Panel(
        padding: const EdgeInsets.all(Space.lg),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${widget.action['title']}', style: text.titleMedium),
          if (widget.action['details'] != null) ...[
            const SizedBox(height: 4),
            Text('${widget.action['details']}', style: text.bodyMedium?.copyWith(color: Palette.muted)),
          ],
          const SizedBox(height: Space.md),
          if (_done)
            Text('Done', style: text.labelLarge?.copyWith(color: Palette.released))
          else
            Wrap(spacing: Space.sm, children: [
              FilledButton(
                style: cancel ? FilledButton.styleFrom(backgroundColor: Palette.problem) : null,
                onPressed: _busy
                    ? null
                    : () async {
                        setState(() => _busy = true);
                        await widget.onConfirm(widget.action);
                        if (mounted) {
                          setState(() {
                            _busy = false;
                            _done = true;
                          });
                        }
                      },
                child: Text(cancel ? 'Confirm cancel' : 'Confirm move'),
              ),
              TextButton(
                onPressed: () => context.go('/my/bookings/${widget.action['booking_id']}'),
                child: const Text('See booking'),
              ),
            ]),
        ]),
      ),
    );
  }
}
