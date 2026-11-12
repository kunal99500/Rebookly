import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:record/record.dart';

import '../app/tokens.dart';
import '../core/api/api_client.dart';
import '../core/api/api_exception.dart';
import 'feedback.dart';

/// Speak instead of typing, in any language. Tap to start, tap again to stop;
/// the words appear in the box so the person can check them before sending. Nothing is stored.
class MicButton extends ConsumerStatefulWidget {
  const MicButton({super.key, required this.onText, this.context = 'onboarding'});

  final ValueChanged<String> onText;
  final String context;   // onboarding or assistant: helps the speech recognition

  @override
  ConsumerState<MicButton> createState() => _MicButtonState();
}

enum _MicState { idle, recording, working }

class _MicButtonState extends ConsumerState<MicButton> {
  final _recorder = AudioRecorder();
  _MicState _state = _MicState.idle;
  String _mime = 'audio/webm';
  Timer? _limit;

  @override
  void dispose() {
    _limit?.cancel();
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    if (!await _recorder.hasPermission()) {
      if (mounted) showMessage(context, 'Allow the microphone in your browser to speak instead of typing.');
      return;
    }
    // Chrome, Edge and Firefox record Opus in WebM; Safari records AAC in MP4.
    final opus = await _recorder.isEncoderSupported(AudioEncoder.opus);
    _mime = opus ? 'audio/webm' : 'audio/mp4';
    await _recorder.start(
      RecordConfig(encoder: opus ? AudioEncoder.opus : AudioEncoder.aacLc, numChannels: 1, sampleRate: 16000),
      path: opus ? 'speech.webm' : 'speech.m4a',
    );
    setState(() => _state = _MicState.recording);
    _limit = Timer(const Duration(minutes: 3), _stop);   // a safety stop for very long recordings
  }

  Future<void> _stop() async {
    _limit?.cancel();
    if (_state != _MicState.recording) return;
    setState(() => _state = _MicState.working);
    try {
      final location = await _recorder.stop();   // on the web: a temporary link to the recording
      if (location == null) throw const ApiException('Nothing was recorded. Try again.');
      final bytes = (await Dio().get<List<int>>(location, options: Options(responseType: ResponseType.bytes))).data ?? const [];
      final form = FormData.fromMap({
        'context': widget.context,
        'audio': MultipartFile.fromBytes(bytes, filename: _mime == 'audio/webm' ? 'speech.webm' : 'speech.m4a',
            contentType: DioMediaType.parse(_mime)),
      });
      final json = await ref.read(apiClientProvider).postForm('/api/voice/transcribe', form);
      final text = (json as Map)['text']?.toString().trim() ?? '';
      if (text.isNotEmpty) widget.onText(text);
    } on ApiException catch (problem) {
      if (mounted) showMessage(context, problem.message);
    } catch (_) {
      if (mounted) showMessage(context, 'We couldn’t use the recording. Please try again or type.');
    } finally {
      if (mounted) setState(() => _state = _MicState.idle);
    }
  }

  @override
  Widget build(BuildContext context) {
    return switch (_state) {
      _MicState.idle => IconButton(
          tooltip: 'Speak instead of typing (any language)',
          icon: const Icon(Icons.mic_none_rounded, color: Palette.forest),
          onPressed: _start,
        ),
      _MicState.recording => IconButton(
          tooltip: 'Stop and use what I said',
          style: IconButton.styleFrom(backgroundColor: Palette.problemBg),
          icon: const Icon(Icons.stop_rounded, color: Palette.problem),
          onPressed: _stop,
        ),
      _MicState.working => const Padding(
          padding: EdgeInsets.all(12),
          child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
        ),
    };
  }
}

/// Adds spoken words to whatever is already in a text box.
void appendSpoken(TextEditingController controller, String words) {
  final current = controller.text.trimRight();
  controller.text = current.isEmpty ? words : '$current $words';
  controller.selection = TextSelection.collapsed(offset: controller.text.length);
}
