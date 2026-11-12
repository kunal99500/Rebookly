import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'owner_page.dart';

/// Point the camera at the client's check-in code. The deposit then goes toward their bill.
class CheckInScreen extends StatelessWidget {
  const CheckInScreen({super.key});

  @override
  Widget build(BuildContext context) => OwnerPage(
        title: 'Check in',
        builder: (context, id, business) => _Scanner(businessId: id),
      );
}

class _Scanner extends ConsumerStatefulWidget {
  const _Scanner({required this.businessId});

  final String businessId;

  @override
  ConsumerState<_Scanner> createState() => _ScannerState();
}

class _ScannerState extends ConsumerState<_Scanner> {
  final _controller = MobileScannerController(detectionSpeed: DetectionSpeed.noDuplicates, formats: const [BarcodeFormat.qrCode]);
  bool _busy = false;
  ({bool ok, String message})? _result;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _checkIn(String token) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _result = null;
    });
    try {
      final json = await ref.read(apiClientProvider).post('/api/owner/businesses/${widget.businessId}/check-in', body: {'token': token.trim()});
      final message = json is Map && json['message'] != null ? '${json['message']}' : 'Checked in.';
      setState(() => _result = (ok: true, message: message));
    } on ApiException catch (problem) {
      setState(() => _result = (ok: false, message: problem.message));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return PageScroll(maxWidth: 560, children: [
      Text('Scan the client’s code', style: text.displaySmall),
      const SizedBox(height: Space.sm),
      Text('They’ll find it in My bookings on their phone. Allow the camera when your browser asks.',
          style: text.bodyLarge?.copyWith(color: Palette.muted)),
      const SizedBox(height: Space.xl),
      ClipRRect(
        borderRadius: BorderRadius.circular(Radii.sheet),
        child: AspectRatio(
          aspectRatio: 1,
          child: MobileScanner(
            controller: _controller,
            onDetect: (capture) {
              final value = capture.barcodes.isEmpty ? null : capture.barcodes.first.rawValue;
              if (value != null) _checkIn(value);
            },
            errorBuilder: (context, error, child) => ColoredBox(
              color: Palette.sage,
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(Space.xl),
                  child: Text('The camera isn’t available. Allow it in your browser, or check the client in from Bookings.',
                      textAlign: TextAlign.center, style: text.bodyMedium),
                ),
              ),
            ),
          ),
        ),
      ),
      const SizedBox(height: Space.lg),
      if (_busy) const LinearProgressIndicator(),
      if (_result != null)
        Panel(
          color: _result!.ok ? Palette.releasedBg : Palette.problemBg,
          child: Row(children: [
            Icon(_result!.ok ? MoneyState.released.icon : MoneyState.problem.icon,
                color: _result!.ok ? Palette.released : Palette.problem),
            const SizedBox(width: Space.md),
            Expanded(child: Text(_result!.message, style: text.titleSmall)),
          ]),
        ),
    ]);
  }
}
