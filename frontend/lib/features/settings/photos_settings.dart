import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import '../../shared/money_state.dart';
import 'settings_common.dart';

typedef _Photos = ({List<Map<String, dynamic>> photos, List<Map<String, dynamic>> services});

final _photosProvider = FutureProvider.autoDispose.family<_Photos, String>((ref, id) async {
  final api = ref.watch(apiClientProvider);
  final results = await Future.wait([api.get('/api/owner/businesses/$id/photos'), api.get('/api/owner/businesses/$id/services')]);
  final photos = results[0];
  return (photos: asList(photos is Map ? photos['photos'] : photos), services: asList(results[1]));
});

/// Real photos only: a cover, up to 8 of the place, and one per service. AI-made images are turned away.
class PhotosSettingsScreen extends StatelessWidget {
  const PhotosSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'Photos',
        subtitle: 'Real photos of your place and your work. Clients trust what they can see.',
        builder: (context, id, business) => _PhotosBody(businessId: id),
      );
}

class _PhotosBody extends ConsumerWidget {
  const _PhotosBody({required this.businessId});

  final String businessId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    void reload() => ref.invalidate(_photosProvider(businessId));
    return AsyncView<_Photos>(
      value: ref.watch(_photosProvider(businessId)),
      onRetry: reload,
      data: (data) {
        final cover = data.photos.where((p) => p['kind'] == 'cover').toList();
        final gallery = data.photos.where((p) => p['kind'] == 'gallery').toList();
        final byService = data.photos.where((p) => p['kind'] == 'service').toList();
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          BusyButton(
            label: 'Add a photo',
            icon: Icons.add_photo_alternate_outlined,
            onPressed: () async {
              final added = await showDialog<bool>(
                context: context,
                builder: (context) => _UploadDialog(businessId: businessId, services: data.services),
              );
              if (added == true) reload();
            },
          ),
          const SizedBox(height: Space.xl),
          _Group(title: 'Cover', subtitle: 'The big photo at the top of your page.', photos: cover, businessId: businessId, onChanged: reload),
          _Group(title: 'Your place', subtitle: 'Up to 8 photos.', photos: gallery, businessId: businessId, onChanged: reload),
          _Group(
            title: 'Services',
            subtitle: 'One photo per service, shown when booking.',
            photos: byService,
            businessId: businessId,
            onChanged: reload,
            caption: (photo) => data.services.where((s) => '${s['id']}' == '${photo['service_id']}').map((s) => '${s['name']}').firstOrNull,
          ),
          if (data.photos.isEmpty)
            Text('No photos yet. A cover photo makes the biggest difference.', style: text.bodyMedium?.copyWith(color: Palette.muted)),
        ]);
      },
    );
  }
}

class _Group extends ConsumerWidget {
  const _Group({required this.title, required this.subtitle, required this.photos, required this.businessId, required this.onChanged, this.caption});

  final String title;
  final String subtitle;
  final List<Map<String, dynamic>> photos;
  final String businessId;
  final VoidCallback onChanged;
  final String? Function(Map<String, dynamic> photo)? caption;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (photos.isEmpty) return const SizedBox.shrink();
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.xl),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SectionHeader(title, subtitle: subtitle),
        Wrap(spacing: Space.md, runSpacing: Space.md, children: [
          for (final photo in photos)
            SizedBox(
              width: 200,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(Radii.card),
                  child: AspectRatio(
                    aspectRatio: 4 / 3,
                    child: Image.network('${photo['thumb_url'] ?? photo['url']}', fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => const ColoredBox(color: Palette.sage)),
                  ),
                ),
                const SizedBox(height: Space.xs),
                Row(children: [
                  Expanded(
                    child: photo['moderation_status'] == 'approved'
                        ? Text(caption?.call(photo) ?? '${photo['alt_text'] ?? ''}', style: text.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis)
                        : StatusPill(photo['moderation_status'] == 'rejected' ? 'Not accepted' : 'Being checked',
                            state: photo['moderation_status'] == 'rejected' ? MoneyState.problem : MoneyState.waiting),
                  ),
                  IconButton(
                    tooltip: 'Remove',
                    icon: const Icon(Icons.delete_outline_rounded, size: 20),
                    onPressed: () async {
                      if (await runSave(context, () => ref.read(apiClientProvider).delete('/api/owner/businesses/$businessId/photos/${photo['id']}'),
                          done: 'Photo removed.')) {
                        onChanged();
                      }
                    },
                  ),
                ]),
              ]),
            ),
        ]),
      ]),
    );
  }
}

class _UploadDialog extends ConsumerStatefulWidget {
  const _UploadDialog({required this.businessId, required this.services});

  final String businessId;
  final List<Map<String, dynamic>> services;

  @override
  ConsumerState<_UploadDialog> createState() => _UploadDialogState();
}

class _UploadDialogState extends ConsumerState<_UploadDialog> {
  PlatformFile? _file;
  String _kind = 'gallery';
  String? _serviceId;
  bool _real = false;
  final _alt = TextEditingController();

  @override
  void dispose() {
    _alt.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    final result = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['jpg', 'jpeg', 'png', 'webp'], withData: true);
    if (result != null && result.files.isNotEmpty) setState(() => _file = result.files.single);
  }

  Future<void> _upload() async {
    final file = _file!;
    final ext = (file.extension ?? 'jpg').toLowerCase();
    final mime = ext == 'png' ? 'image/png' : (ext == 'webp' ? 'image/webp' : 'image/jpeg');
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(file.bytes!, filename: file.name, contentType: DioMediaType.parse(mime)),
      'kind': _kind,
      if (_kind == 'service' && _serviceId != null) 'service_id': _serviceId,
      if (_alt.text.trim().isNotEmpty) 'alt_text': _alt.text.trim(),
      'confirm_real_photo': _real ? 'true' : 'false',
    });
    if (await runSave(context, () => ref.read(apiClientProvider).postForm('/api/owner/businesses/${widget.businessId}/photos', form),
        done: 'Photo added.')) {
      if (mounted) Navigator.of(context).pop(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final tooBig = (_file?.size ?? 0) > 5 * 1024 * 1024;
    final ready = _file?.bytes != null && !tooBig && _real && (_kind != 'service' || _serviceId != null);
    return AlertDialog(
      title: const Text('Add a photo'),
      content: SizedBox(
        width: 440,
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            OutlinedButton.icon(
              onPressed: _pick,
              icon: const Icon(Icons.upload_file_rounded, size: 20),
              label: Text(_file == null ? 'Choose a photo (JPEG, PNG or WebP)' : _file!.name, overflow: TextOverflow.ellipsis),
            ),
            if (_file?.bytes != null) ...[
              const SizedBox(height: Space.md),
              ClipRRect(
                borderRadius: BorderRadius.circular(Radii.control),
                child: Image.memory(_file!.bytes!, height: 160, width: double.infinity, fit: BoxFit.cover),
              ),
            ],
            if (tooBig) Text('That photo is over 5 MB. Choose a smaller one.', style: text.bodyMedium?.copyWith(color: Palette.problem)),
            const SizedBox(height: Space.md),
            Wrap(spacing: Space.sm, children: [
              for (final (kind, label) in const [('cover', 'Cover'), ('gallery', 'Your place'), ('service', 'A service')])
                ChoiceChip(label: Text(label), selected: _kind == kind, showCheckmark: false, onSelected: (_) => setState(() => _kind = kind)),
            ]),
            if (_kind == 'service') ...[
              const SizedBox(height: Space.md),
              DropdownMenu<String>(
                label: const Text('Which service'),
                width: 400,
                dropdownMenuEntries: [for (final s in widget.services) DropdownMenuEntry(value: '${s['id']}', label: '${s['name']}')],
                onSelected: (value) => setState(() => _serviceId = value),
              ),
            ],
            const SizedBox(height: Space.md),
            TextField(controller: _alt, maxLength: 200, decoration: const InputDecoration(labelText: 'Describe it (helps people using screen readers)')),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: _real,
              onChanged: (value) => setState(() => _real = value ?? false),
              title: const Text('This is a real, unedited photo of my business'),
              subtitle: const Text('Not made or changed with AI.'),
            ),
          ]),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
        BusyButton(label: 'Upload', onPressed: ready ? _upload : null),
      ],
    );
  }
}
