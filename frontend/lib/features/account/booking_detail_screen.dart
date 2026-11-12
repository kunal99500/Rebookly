import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/tokens.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/money.dart';
import '../../core/format/time.dart';
import '../../shared/client_shell.dart';
import '../../shared/feedback.dart';
import '../../shared/hold_ticket.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import '../booking/booking_data.dart';
import 'account_data.dart';
import 'booking_status.dart';

/// One booking: the ticket, the check-in code, receipts, and moving, cancelling or reviewing it.
class BookingDetailScreen extends ConsumerWidget {
  const BookingDetailScreen({super.key, required this.bookingId});

  final String bookingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ClientShell(
      child: AsyncView<ClientBooking>(
        value: ref.watch(bookingDetailProvider(bookingId)),
        page: true,
        onRetry: () => ref.invalidate(bookingDetailProvider(bookingId)),
        data: (booking) => _Detail(booking: booking),
      ),
    );
  }
}

class _Detail extends ConsumerWidget {
  const _Detail({required this.booking});

  final ClientBooking booking;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final now = DateTime.now();
    final status = bookingStatus(booking, now);
    final upcoming = booking.status == 'confirmed' && booking.startsAt.isAfter(now);
    final services = booking.items.isEmpty ? booking.serviceName : booking.items.map((i) => i.name).join(' + ');

    return PageScroll(maxWidth: 720, children: [
      TextButton.icon(
        onPressed: () => context.go('/my'),
        icon: const Icon(Icons.arrow_back_rounded, size: 18),
        label: const Text('My bookings'),
      ),
      const SizedBox(height: Space.sm),
      Row(children: [
        Expanded(child: Text(booking.businessName, style: text.displaySmall)),
      ]),
      const SizedBox(height: Space.sm),
      Wrap(spacing: Space.md, runSpacing: Space.sm, crossAxisAlignment: WrapCrossAlignment.center, children: [
        StatusPill(status.label, state: status.state),
        if (booking.confirmationNumber != null) Text('Reference ${booking.confirmationNumber}', style: text.bodySmall),
      ]),
      const SizedBox(height: Space.xl),
      DecoratedBox(
        decoration: BoxDecoration(color: Palette.sage, borderRadius: BorderRadius.circular(Radii.sheet)),
        child: Padding(
          padding: const EdgeInsets.all(Space.lg),
          child: HoldTicket(
            title: services,
            lines: [
              '${formatDayTime(booking.startsAt, booking.timezone)} to ${formatTime(booking.endsAt, booking.timezone)}',
              if (booking.staffName != null) 'With ${booking.staffName}',
              if (booking.attendeeName != null) 'For ${booking.attendeeName}',
            ],
            held: formatMoney(booking.heldAmount, booking.currency),
            heldCaption: booking.status == 'confirmed' ? 'kept aside, not taken' : 'amount that was kept aside',
            payLater: formatMoney(booking.price, booking.currency),
            payLaterCaption: 'total for the visit',
          ),
        ),
      ),
      if (upcoming && booking.checkInToken != null) ...[
        const SizedBox(height: Space.xl),
        _CheckInCode(token: booking.checkInToken!),
      ],
      if (upcoming) ...[
        const SizedBox(height: Space.xl),
        Wrap(spacing: Space.md, runSpacing: Space.md, children: [
          OutlinedButton.icon(
            onPressed: () => context.go('/my/bookings/${booking.id}/move'),
            icon: const Icon(Icons.schedule_rounded, size: 20),
            label: const Text('Move to another time'),
          ),
          OutlinedButton.icon(
            onPressed: () => _cancel(context, ref),
            style: OutlinedButton.styleFrom(foregroundColor: Palette.problem),
            icon: const Icon(Icons.event_busy_outlined, size: 20),
            label: const Text('Cancel booking'),
          ),
        ]),
      ],
      if (booking.status == 'attended') ...[
        const SizedBox(height: 40),
        _ReviewCard(bookingId: booking.id),
      ],
      const SizedBox(height: 40),
      _Receipts(bookingId: booking.id),
    ]);
  }

  Future<void> _cancel(BuildContext context, WidgetRef ref) async {
    final cancelled = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Palette.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.sheet))),
      builder: (context) => _CancelSheet(booking: booking),
    );
    if (cancelled == true && context.mounted) {
      ref.invalidate(bookingDetailProvider(booking.id));
      ref.invalidate(myBookingsProvider);
      ref.invalidate(bookingDocumentsProvider(booking.id));
      showMessage(context, 'Booking cancelled.');
    }
  }
}

class _CheckInCode extends StatelessWidget {
  const _CheckInCode({required this.token});

  final String token;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Panel(
      child: Row(children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(Radii.control)),
          child: QrImageView(data: token, size: 132, padding: EdgeInsets.zero, semanticsLabel: 'Check-in code'),
        ),
        const SizedBox(width: Space.xl),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Your check-in code', style: text.titleMedium),
            const SizedBox(height: Space.sm),
            Text(
              'Show this when you arrive. The business scans it to check you in, and the amount kept aside counts toward your bill.',
              style: text.bodyMedium?.copyWith(color: Palette.muted),
            ),
          ]),
        ),
      ]),
    );
  }
}

class _CancelSheet extends ConsumerStatefulWidget {
  const _CancelSheet({required this.booking});

  final ClientBooking booking;

  @override
  ConsumerState<_CancelSheet> createState() => _CancelSheetState();
}

class _CancelSheetState extends ConsumerState<_CancelSheet> {
  late final Future<CancelPreview> _preview = ref.read(accountApiProvider).cancelPreview(widget.booking.id);
  bool _busy = false;
  String? _error;

  Future<void> _confirm() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(accountApiProvider).cancel(widget.booking.id);
      if (mounted) Navigator.of(context).pop(true);
    } on ApiException catch (problem) {
      if (mounted) setState(() => _error = problem.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 24, 24, 24),
        child: FutureBuilder<CancelPreview>(
          future: _preview,
          builder: (context, snapshot) {
            if (snapshot.hasError) return ErrorPanel(error: snapshot.error!);
            if (!snapshot.hasData) return const SizedBox(height: 160, child: Center(child: CircularProgressIndicator()));
            final preview = snapshot.data!;
            return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Cancel this booking?', style: text.headlineSmall),
              const SizedBox(height: Space.sm),
              Text(preview.reason, style: text.bodyMedium?.copyWith(color: Palette.muted)),
              const SizedBox(height: Space.xl),
              _Line(label: preview.needsOwnerApproval ? 'May be kept (the business decides)' : 'Kept as a fee',
                  amount: formatMoney(preview.fee, preview.currency), color: preview.isFree ? Palette.ink : Palette.problem),
              _Line(label: 'Released back to you', amount: formatMoney(preview.released, preview.currency), color: Palette.released),
              if (!preview.isFree) ...[
                const SizedBox(height: Space.md),
                Text(
                  'If someone else books this time, the fee is usually dropped. Moving the booking instead may cost nothing.',
                  style: text.bodySmall,
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: Space.md),
                Text(_error!, style: text.bodyMedium?.copyWith(color: Palette.problem)),
              ],
              const SizedBox(height: Space.xl),
              Row(children: [
                Expanded(child: OutlinedButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Keep booking'))),
                const SizedBox(width: Space.md),
                Expanded(
                  child: FilledButton(
                    onPressed: _busy ? null : _confirm,
                    style: FilledButton.styleFrom(backgroundColor: Palette.problem),
                    child: _busy
                        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white))
                        : const Text('Cancel booking'),
                  ),
                ),
              ]),
            ]);
          },
        ),
      ),
    );
  }
}

class _Line extends StatelessWidget {
  const _Line({required this.label, required this.amount, required this.color});

  final String label;
  final String amount;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        Expanded(child: Text(label, style: text.bodyLarge)),
        Text(amount, style: text.titleLarge?.copyWith(color: color, fontFeatures: Fonts.tabular)),
      ]),
    );
  }
}

class _Receipts extends ConsumerWidget {
  const _Receipts({required this.bookingId});

  final String bookingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader('Receipts', subtitle: 'Every confirmation, receipt and release notice for this booking.'),
      AsyncView<List<DocumentLink>>(
        value: ref.watch(bookingDocumentsProvider(bookingId)),
        loading: const SkeletonList(rows: 1),
        onRetry: () => ref.invalidate(bookingDocumentsProvider(bookingId)),
        data: (documents) => documents.isEmpty
            ? Text('Receipts appear here once the booking is confirmed.', style: text.bodyMedium?.copyWith(color: Palette.muted))
            : Column(children: [
                for (final document in documents)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.receipt_long_outlined, color: Palette.forest),
                    title: Text(document.title, style: text.titleSmall),
                    subtitle: document.number == null ? null : Text(document.number!, style: text.bodySmall),
                    trailing: const Icon(Icons.open_in_new_rounded, size: 18, color: Palette.muted),
                    onTap: () => launchUrl(Uri.parse(document.url), webOnlyWindowName: '_blank'),
                  ),
              ]),
      ),
    ]);
  }
}

class _ReviewCard extends ConsumerStatefulWidget {
  const _ReviewCard({required this.bookingId});

  final String bookingId;

  @override
  ConsumerState<_ReviewCard> createState() => _ReviewCardState();
}

class _ReviewCardState extends ConsumerState<_ReviewCard> {
  int _rating = 0;
  final _comment = TextEditingController();
  bool _editing = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _save(bool existing) async {
    if (_rating == 0) {
      setState(() => _error = 'Choose how many stars.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(accountApiProvider).writeReview(widget.bookingId, _rating, _comment.text.trim(), editing: existing);
      ref.invalidate(reviewStatusProvider(widget.bookingId));
      if (mounted) {
        setState(() => _editing = false);
        showMessage(context, 'Thanks for your review.');
      }
    } on ApiException catch (problem) {
      if (mounted) setState(() => _error = problem.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return AsyncView<ReviewStatus>(
      value: ref.watch(reviewStatusProvider(widget.bookingId)),
      loading: const SizedBox.shrink(),
      data: (status) {
        final review = status.review;
        if (review != null && !_editing) {
          return Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Your review', style: text.titleMedium),
              const SizedBox(height: Space.sm),
              _Stars(rating: review.rating),
              if (review.comment != null) ...[const SizedBox(height: Space.sm), Text(review.comment!, style: text.bodyLarge)],
              if (review.ownerReply != null) ...[
                const SizedBox(height: Space.md),
                Text('Reply from the business: ${review.ownerReply}', style: text.bodySmall),
              ],
              if (status.canEdit)
                TextButton(
                  onPressed: () => setState(() {
                    _editing = true;
                    _rating = review.rating;
                    _comment.text = review.comment ?? '';
                  }),
                  child: const Text('Edit review'),
                ),
            ]),
          );
        }
        if (review == null && !status.canReview) return const SizedBox.shrink();
        return Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(review == null ? 'How was your visit?' : 'Edit your review', style: text.titleMedium),
            const SizedBox(height: Space.sm),
            Text('Reviews only come from people who really visited. Shown with your first name and initial.',
                style: text.bodySmall),
            const SizedBox(height: Space.md),
            _Stars(rating: _rating, onChanged: (value) => setState(() => _rating = value)),
            const SizedBox(height: Space.md),
            TextField(
              controller: _comment,
              maxLength: 1000,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'Anything to add? (optional)'),
            ),
            if (_error != null) Text(_error!, style: text.bodyMedium?.copyWith(color: Palette.problem)),
            const SizedBox(height: Space.sm),
            FilledButton(onPressed: _busy ? null : () => _save(review != null), child: const Text('Post review')),
          ]),
        );
      },
    );
  }
}

class _Stars extends StatelessWidget {
  const _Stars({required this.rating, this.onChanged});

  final int rating;
  final ValueChanged<int>? onChanged;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        for (var i = 1; i <= 5; i++)
          IconButton(
            tooltip: '$i star${i == 1 ? '' : 's'}',
            onPressed: onChanged == null ? null : () => onChanged!(i),
            icon: Icon(i <= rating ? Icons.star_rounded : Icons.star_outline_rounded,
                color: i <= rating ? Palette.waiting : Palette.faint, size: 30),
          ),
      ]);
}
