import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/tokens.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../shared/feedback.dart';
import '../../shared/layout.dart';
import 'settings_common.dart';

/// Where the business is: an address search that fills everything in, or typing it yourself.
class LocationSettingsScreen extends StatelessWidget {
  const LocationSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) => SettingsPage(
        title: 'Location',
        subtitle: 'So nearby clients can find you, and so tax is worked out for the right place.',
        builder: (context, id, business) => _Location(businessId: id, business: business),
      );
}

class _Location extends ConsumerStatefulWidget {
  const _Location({required this.businessId, required this.business});

  final String businessId;
  final Map<String, dynamic> business;

  @override
  ConsumerState<_Location> createState() => _LocationState();
}

class _LocationState extends ConsumerState<_Location> {
  late final b = widget.business;
  final _search = TextEditingController();
  late final _address = TextEditingController(text: '${b['address'] ?? ''}');
  late final _city = TextEditingController(text: '${b['city'] ?? ''}');
  late final _postal = TextEditingController(text: '${b['postal_code'] ?? ''}');
  late String _country = '${b['country_code'] ?? 'IN'}';
  late String? _region = b['region_code']?.toString();
  late Object? _lat = b['latitude'];
  late Object? _lon = b['longitude'];
  String _source = 'manual';
  List<Map<String, dynamic>> _regions = const [];
  List<Map<String, dynamic>> _results = const [];
  List<String> _warnings = const [];
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _loadRegions();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    for (final c in [_search, _address, _city, _postal]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _loadRegions() async {
    try {
      final json = await ref.read(apiClientProvider).get('/api/geo/countries/$_country/regions');
      if (mounted) setState(() => _regions = asList(json is Map ? json['regions'] : json));
    } on ApiException {
      if (mounted) setState(() => _regions = const []);
    }
  }

  void _onSearch(String query) {
    _debounce?.cancel();
    if (query.trim().length < 3) return;
    _debounce = Timer(const Duration(milliseconds: 600), () async {
      try {
        final json = await ref.read(apiClientProvider).get('/api/geo/search', query: {'q': query.trim(), 'country': _country});
        if (mounted) setState(() => _results = asList(json is Map ? json['results'] : json));
      } on ApiException catch (problem) {
        if (mounted) showMessage(context, problem.message);
      }
    });
  }

  void _use(Map<String, dynamic> place) {
    setState(() {
      _address.text = '${place['address'] ?? place['display_name'] ?? ''}';
      _city.text = '${place['city'] ?? ''}';
      _postal.text = '${place['postal_code'] ?? ''}';
      if (place['country_code'] != null) _country = '${place['country_code']}'.toUpperCase();
      _region = place['region_code']?.toString();
      _lat = place['latitude'];
      _lon = place['longitude'];
      _source = 'search';
      _results = const [];
      _search.clear();
    });
    _loadRegions();
  }

  Future<void> _save() async {
    await runSave(context, () async {
      final json = asMap(await ref.read(apiClientProvider).put('/api/owner/businesses/${widget.businessId}/location', body: {
        'country_code': _country,
        if (_region != null) 'region_code': _region,
        'city': _city.text.trim(),
        if (_postal.text.trim().isNotEmpty) 'postal_code': _postal.text.trim(),
        'address': _address.text.trim(),
        if (_lat != null && _lon != null) 'latitude': '$_lat',
        if (_lat != null && _lon != null) 'longitude': '$_lon',
        'source': _lat != null ? _source : 'manual',
      }));
      setState(() => _warnings = [for (final w in (json['warnings'] as List? ?? const [])) '$w']);
      ref.invalidate(businessDetailProvider(widget.businessId));
    });
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      TextField(
        controller: _search,
        onChanged: _onSearch,
        decoration: const InputDecoration(
          labelText: 'Search for your address',
          hintText: 'Shop name, street, area or landmark',
          prefixIcon: Icon(Icons.search_rounded),
        ),
      ),
      for (final place in _results.take(6))
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.place_outlined, color: Palette.forest),
          title: Text('${place['display_name'] ?? place['address'] ?? ''}', maxLines: 2, overflow: TextOverflow.ellipsis),
          onTap: () => _use(place),
        ),
      const SizedBox(height: Space.xl),
      const SectionHeader('Address', subtitle: 'Filled in from the search, or type it yourself.'),
      TextField(controller: _address, maxLines: 2, decoration: const InputDecoration(labelText: 'Street address')),
      const SizedBox(height: Space.md),
      Wrap(spacing: Space.md, runSpacing: Space.md, children: [
        SizedBox(width: 240, child: TextField(controller: _city, decoration: const InputDecoration(labelText: 'City or town'))),
        SizedBox(width: 160, child: TextField(controller: _postal, decoration: const InputDecoration(labelText: 'Postal code'))),
        if (_regions.isNotEmpty)
          DropdownMenu<String>(
            key: ValueKey('$_country$_region'),
            initialSelection: _region,
            label: const Text('State or region'),
            width: 260,
            enableFilter: true,
            requestFocusOnTap: true,
            menuHeight: 320,
            dropdownMenuEntries: [
              for (final region in _regions) DropdownMenuEntry(value: '${region['code']}', label: '${region['name']}'),
            ],
            onSelected: (value) => setState(() => _region = value),
          ),
      ]),
      const SizedBox(height: Space.md),
      Row(children: [
        Icon(_lat != null ? Icons.my_location_rounded : Icons.location_disabled_outlined,
            size: 18, color: _lat != null ? Palette.released : Palette.muted),
        const SizedBox(width: Space.sm),
        Expanded(
          child: Text(
            _lat != null ? 'Map position set. Nearby clients can find you.' : 'No map position yet. Pick a search result to add one.',
            style: text.bodySmall,
          ),
        ),
      ]),
      if (_warnings.isNotEmpty) ...[
        const SizedBox(height: Space.lg),
        Panel(
          color: Palette.waitingBg,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            for (final warning in _warnings) Text('• $warning', style: text.bodyMedium),
          ]),
        ),
      ],
      const SizedBox(height: Space.xl),
      BusyButton(label: 'Save location', onPressed: _save),
    ]);
  }
}
