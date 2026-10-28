from . import settings as _settings
import copy
from decimal import Decimal
from . import texesc
from . import style as _style
SCHEMA_VERSION = 1
CHART_TYPES = ('line', 'waterfall', 'bar', 'scatter', 'hexbin')
_REQUIRED = object()
_COMMON_FIELDS = {'schema': SCHEMA_VERSION, 'type': _REQUIRED, 'name': _REQUIRED, 'outdir': _REQUIRED, 'formats': None, 'preview': True, 'data': _REQUIRED, 'xtitle': None, 'ytitle': _REQUIRED, 'xlim': None, 'ylim': None, 'xticks': None, 'yticks': None, 'xtick_labels': None, 'ytick_labels': None, 'xtick_format': None, 'ytick_format': None, 'xtick_rotation': None, 'grid': None, 'log_x': False, 'log_y': False, 'reference_lines': None, 'legend': None, 'xtitle_left': None, 'xtitle_right': None, 'reduce': None, 'escape_labels': False}
_LINE_FIELDS = {'x': _REQUIRED, 'series': _REQUIRED, 'bands': None, 'emphasis': None, 'step': None, 'step_joint': 'circles'}
_WATERFALL_FIELDS = {'bars': _REQUIRED, 'row_filter': None, 'sum_check_tolerance': 1e-09}
_WATERFALL_BAR_FIELDS = {'value_col': _REQUIRED, 'label': _REQUIRED, 'kind': 'delta', 'sd_col': None}
_BAR_FIELDS = {'category': _REQUIRED, 'value': _REQUIRED, 'category_label': None, 'group': None, 'group_label': None, 'series': None, 'series_label': None, 'colors': None, 'baseline': 0.0, 'se': None, 'lower': None, 'upper': None, 'se_on': 'total'}
_SCATTER_FIELDS = {'x': _REQUIRED, 'series': _REQUIRED, 'rasterize': None}
_HEXBIN_FIELDS = {'x': _REQUIRED, 'y': _REQUIRED, 'value': None, 'cuts': None, 'bins': None, 'color_scale': 'cuts', 'key_ticks': None, 'key_title': None, 'srange': (0.3, 1.0), 'sizeprop': True, 'size_scale': 'linear', 'hex_half_height': None, 'hex_half_width': None, 'hex_shape': 'regular'}
_SCATTER_SERIES_FIELDS = {'y': _REQUIRED, 'x': None, 'label': None, 'color': None, 'symbol': None, 'size': None, 'edge_width': None, 'alpha': None}
_LEGEND_FIELDS = {'show': True, 'cols': None, 'position': 'bottom', 'order': None, 'labels': None, 'fontsize': None}
_SERIES_FIELDS = {'y': _REQUIRED, 'label': None, 'color': None, 'pattern': None, 'linewidth': None, 'marker': None, 'alpha': None, 'reduce': None, 'jumps': None}
_BAND_FIELDS = {'lo': _REQUIRED, 'hi': _REQUIRED, 'color': None, 'alpha': None, 'label': None}
_REFLINE_FIELDS = {'axis': _REQUIRED, 'at': _REQUIRED, 'label': None}
_REDUCE_FIELDS = {'enabled': True, 'max_points': None, 'method': None}
_TEXT_FIELDS = ('xtitle', 'ytitle', 'xtick_labels', 'ytick_labels')

def _check_keys(given, allowed, where):
    unknown = sorted(set(given) - set(allowed))
    if unknown:
        raise ValueError(f'{where}: unknown key(s) {unknown}. Allowed: {sorted(allowed)}. Unknown keys are an error, not ignored -- a typo would silently drop the setting.')

def _fill(given, table, where):
    _check_keys(given, table, where)
    out = {}
    for key, default in table.items():
        if key in given:
            out[key] = given[key]
        elif default is _REQUIRED:
            raise ValueError(f'{where}: required key {key!r} is missing.')
        else:
            out[key] = copy.deepcopy(default)
    return out

def _normalize_ticks(value, where):
    if value is None or isinstance(value, (list, tuple)):
        return list(value) if value is not None else None
    if not isinstance(value, dict):
        raise ValueError(f"{where}: ticks must be a list, {{'start':a,'stop':b,'step':c}} (Stata's xlabel(a(c)b)), or {{'count':n}} (Stata's xlabel(#n)); got {value!r}")
    _check_keys(value, {'start', 'stop', 'step', 'count'}, where)
    if 'count' in value:
        if set(value) != {'count'}:
            raise ValueError(f"{where}: 'count' cannot be combined with start/stop/step.")
        count = int(value['count'])
        if count < 2:
            raise ValueError(f"{where}: 'count' must be >= 2, got {count}.")
        return {'count': count}
    for key in ('start', 'stop', 'step'):
        if key not in value:
            raise ValueError(f'{where}: range form needs start, stop and step; missing {key!r}.')
    start, stop, step = (float(value[k]) for k in ('start', 'stop', 'step'))
    if step <= 0:
        raise ValueError(f'{where}: step must be > 0, got {step}.')
    if stop < start:
        raise ValueError(f'{where}: stop ({stop}) is below start ({start}).')
    ticks = []
    position = start
    # Expand inclusive tick ranges with decimal arithmetic.
    steps = int((Decimal(str(stop)) - Decimal(str(start))) // Decimal(str(step)))
    for index in range(steps + 1):
        position = min(start + index * step, stop)
        ticks.append(position)
    return ticks

def _normalize_reduce(value, where):
    if value is None:
        return None
    if value is False:
        return {'enabled': False, 'max_points': None, 'method': None}
    if value is True:
        return {'enabled': True, 'max_points': None, 'method': None}
    if not isinstance(value, dict):
        raise ValueError(f"{where}: 'reduce' must be True, False, or a dict {{'enabled','max_points','method'}}; got {value!r}")
    out = _fill(value, _REDUCE_FIELDS, where)
    if out['max_points'] is not None:
        out['max_points'] = int(out['max_points'])
        if out['max_points'] < 2:
            raise ValueError(f"{where}: max_points must be >= 2, got {out['max_points']}.")
    return out

def _normalize_pattern(value, where, allow_furniture=False):
    if value is None:
        return None
    allowed = ('solid', 'none') + tuple(_settings.constant('style', 'PATTERN_ORDER')) + (('furniture',) if allow_furniture else ())
    if value not in allowed:
        extra = '' if allow_furniture else " (`furniture' is reserved for reference lines)"
        raise ValueError(f"{where}: unknown line pattern {value!r}. Allowed: {list(('solid', 'none') + tuple(_settings.constant('style', 'PATTERN_ORDER')))}.{extra}")
    return value

def _normalize_linewidth(value, where):
    if value is None:
        return None
    if isinstance(value, str):
        if value not in _settings.constant('style', 'STATA_LINEWIDTH_RELSIZE'):
            raise ValueError(f"{where}: unknown linewidth style {value!r}. Allowed: {list(_settings.constant('style', 'STATA_LINEWIDTH_RELSIZE'))}, or a number of points.")
        return value
    width = float(value)
    if width < 0:
        raise ValueError(f'{where}: linewidth must be >= 0, got {width}.')
    return width

def normalize(raw):
    if not isinstance(raw, dict):
        raise ValueError(f'a spec must be a dict, got {type(raw).__name__}')
    _settings.finite(raw)
    if not isinstance(raw.get('name'), str) or not _settings.NAME.fullmatch(raw['name']):
        raise ValueError('name must be a safe filename stem beginning with a letter')
    if raw.get('escape_labels'):
        raw = _escape_labels(raw)
    chart_type = raw.get('type')
    if chart_type not in CHART_TYPES:
        raise ValueError(f"spec['type'] must be one of {list(CHART_TYPES)}, got {chart_type!r}")
    type_fields = _fields('_' + chart_type.upper() + '_FIELDS')
    allowed = dict(_COMMON_FIELDS)
    allowed.update(type_fields)
    spec = _fill(raw, allowed, f'spec (type={chart_type})')
    if type(spec['schema']) is not int or spec['schema'] != SCHEMA_VERSION:
        raise ValueError(f"spec schema version {spec['schema']} but this twoway_pgf understands {SCHEMA_VERSION}. Rebuild the spec from its producing code.")
    for field in ('xlim', 'ylim'):
        value = spec[field]
        if value is None:
            continue
        if isinstance(value, (int, float)) or isinstance(value, str):
            raise ValueError(f"spec['{field}'] must be a two-element list [lo, hi], not {value!r}. Use None for a bound that should come from the data.")
        bounds = list(value)
        if len(bounds) != 2:
            raise ValueError(f"spec['{field}'] must have exactly two elements [lo, hi]; got {len(bounds)}: {value!r}")
        bounds = [None if b is None else float(b) for b in bounds]
        if bounds[0] is None and bounds[1] is None:
            raise ValueError(f"spec['{field}'] = [None, None] says nothing. Drop the field to take both ends from the data.")
        if bounds[0] is not None and bounds[1] is not None and (bounds[0] >= bounds[1]):
            raise ValueError(f"spec['{field}'] lower bound {bounds[0]} is not below the upper bound {bounds[1]}.")
        spec[field] = bounds
    for axis in ('x', 'y'):
        spec[f'{axis}ticks'] = _normalize_ticks(spec[f'{axis}ticks'], f"spec['{axis}ticks']")
    if spec['grid'] is not None and spec['grid'] not in ('x', 'y', 'both', 'none'):
        raise ValueError(f"spec['grid'] must be 'x', 'y', 'both', 'none' or None (scheme default); got {spec['grid']!r}")
    for axis in ('x', 'y'):
        ticks, labels = (spec[f'{axis}ticks'], spec[f'{axis}tick_labels'])
        if labels is not None:
            if not isinstance(ticks, list):
                raise ValueError(f"spec['{axis}tick_labels'] needs an explicit list in spec['{axis}ticks'] to attach to.")
            if len(labels) != len(ticks):
                raise ValueError(f"spec['{axis}tick_labels'] has {len(labels)} entries but spec['{axis}ticks'] has {len(ticks)}.")
    spec['reduce'] = _normalize_reduce(spec['reduce'], "spec['reduce']")
    if spec['reference_lines'] is not None:
        lines = []
        for index, raw_line in enumerate(spec['reference_lines']):
            where = f"spec['reference_lines'][{index}]"
            line = _fill(raw_line, _fields('_REFLINE_FIELDS'), where)
            if line['axis'] not in ('x', 'y'):
                raise ValueError(f"{where}: 'axis' must be 'x' or 'y', got {line['axis']!r}")
            line['at'] = float(line['at'])
            line['pattern'] = _normalize_pattern(line['pattern'], f"{where}['pattern']", allow_furniture=True)
            line['linewidth'] = _normalize_linewidth(line['linewidth'], f"{where}['linewidth']")
            texesc.validate(line['label'], f"{where}['label']")
            lines.append(line)
        spec['reference_lines'] = lines
    for key in ('xtitle_left', 'xtitle_right', 'key_title'):
        if key not in spec:
            continue
        if spec[key] is not None:
            spec[key] = texesc.translate_glyphs(str(spec[key]))
            texesc.validate(spec[key], f'spec[{key!r}]')
            spec[key] = texesc.unescape_newlines(spec[key])
    if spec['legend'] is not None:
        legend = _fill(spec['legend'], _LEGEND_FIELDS, "spec['legend']")
        if legend['position'] not in ('bottom', 'right', 'separate', 'none'):
            raise ValueError(f"spec['legend']['position'] must be 'bottom', 'right', 'separate' or 'none'; 'best' is unsupported for figure legends; got {legend['position']!r}")
        if legend['cols'] is not None:
            legend['cols'] = int(legend['cols'])
            if legend['cols'] < 1:
                raise ValueError("spec['legend']['cols'] must be >= 1.")
        if legend['labels'] is not None:
            texesc.validate_all({"spec['legend']['labels']": legend['labels']})
        if legend['fontsize'] is not None:
            if isinstance(legend['fontsize'], str):
                if legend['fontsize'] not in _settings.constant('style', 'STATA_TEXTSIZE_RELSIZE'):
                    raise ValueError(f"spec['legend']['fontsize'] must be a Stata gsize name {sorted(_settings.constant('style', 'STATA_TEXTSIZE_RELSIZE'))} or a number of points; got {legend['fontsize']!r}")
            else:
                legend['fontsize'] = float(legend['fontsize'])
                if legend['fontsize'] <= 0:
                    raise ValueError(f"spec['legend']['fontsize'] in points must be > 0, got {legend['fontsize']}.")
        spec['legend'] = legend
    if chart_type == 'line':
        if not spec['series']:
            raise ValueError("spec['series'] must list at least one series.")
        series = []
        for index, raw_series in enumerate(spec['series']):
            where = f"spec['series'][{index}]"
            entry = _fill(raw_series, _SERIES_FIELDS, where)
            entry['pattern'] = _normalize_pattern(entry['pattern'], f"{where}['pattern']")
            entry['linewidth'] = _normalize_linewidth(entry['linewidth'], f"{where}['linewidth']")
            entry['reduce'] = _normalize_reduce(entry['reduce'], f"{where}['reduce']")
            if entry['alpha'] is not None:
                entry['alpha'] = float(entry['alpha'])
                if not 0 <= entry['alpha'] <= 1:
                    raise ValueError(f"{where}['alpha'] must be in 0..1, got {entry['alpha']}")
            texesc.validate(entry['label'], f"{where}['label']")
            series.append(entry)
        spec['series'] = series
        if spec['bands'] is not None:
            bands = []
            for index, raw_band in enumerate(spec['bands']):
                where = f"spec['bands'][{index}]"
                band = _fill(raw_band, _BAND_FIELDS, where)
                if band['alpha'] is not None:
                    band['alpha'] = float(band['alpha'])
                    if not 0 <= band['alpha'] <= 1:
                        raise ValueError(f"{where}['alpha'] must be in 0..1.")
                texesc.validate(band['label'], f"{where}['label']")
                bands.append(band)
            spec['bands'] = bands
    elif chart_type == 'scatter':
        if not spec['series']:
            raise ValueError("spec['series'] must list at least one series.")
        series = []
        for index, raw_series in enumerate(spec['series']):
            where = f"spec['series'][{index}]"
            entry = _fill(raw_series, _SCATTER_SERIES_FIELDS, where)
            if entry['symbol'] is not None:
                if entry['symbol'] not in _settings.constant('style', 'STATA_SYMBOL_MARKER'):
                    raise ValueError(f"{where}['symbol'] = {entry['symbol']!r} is not a Stata msymbol name. Known: {sorted(_settings.constant('style', 'STATA_SYMBOL_MARKER'))}")
            if entry['size'] is not None:
                if isinstance(entry['size'], str):
                    if entry['size'] not in _settings.constant('style', 'STATA_SYMBOLSIZE_RELSIZE'):
                        raise ValueError(f"{where}['size'] = {entry['size']!r} is not a Stata msize name. Known: {sorted(_settings.constant('style', 'STATA_SYMBOLSIZE_RELSIZE'))}, or give a number of points.")
                else:
                    entry['size'] = float(entry['size'])
                    if entry['size'] <= 0:
                        raise ValueError(f"{where}['size'] in points must be > 0, got {entry['size']}.")
            if entry['edge_width'] is not None:
                entry['edge_width'] = _normalize_linewidth(entry['edge_width'], f"{where}['edge_width']")
            if entry['alpha'] is not None:
                entry['alpha'] = float(entry['alpha'])
                if not 0 <= entry['alpha'] <= 1:
                    raise ValueError(f"{where}['alpha'] must be in 0..1, got {entry['alpha']}")
            texesc.validate(entry['label'], f"{where}['label']")
            series.append(entry)
        spec['series'] = series
        if spec['rasterize'] is not None and (not isinstance(spec['rasterize'], bool)):
            raise ValueError(f"spec['rasterize'] must be True, False, or None for automatic; got {spec['rasterize']!r}")
        spec['raster_dpi'] = float(spec['raster_dpi'])
        if spec['raster_dpi'] <= 0:
            raise ValueError(f"spec['raster_dpi'] must be > 0, got {spec['raster_dpi']}")
        if spec['reduce'] not in (None, False) and spec['reduce'].get('enabled'):
            raise ValueError("spec['reduce'] is set for a scatter, but scatter does not reduce: dropping a marker removes ink, and on a dense cloud the ink density IS the content. Plot fewer points upstream (the project's 'binscatter' figures are pre-binned with xtile+collapse) rather than asking the backend to thin them.")
    elif chart_type == 'hexbin':
        if spec['bins'] is not None:
            bins = float(spec['bins'])
            if bins <= 0 or bins != int(bins):
                raise ValueError("spec['bins'] must be a positive integer.")
            spec['bins'] = int(bins)
        for key in ('hex_half_height', 'hex_half_width'):
            if spec[key] is not None:
                spec[key] = float(spec[key])
                if spec[key] <= 0:
                    raise ValueError(f"spec['{key}'] must be positive.")
    elif chart_type == 'waterfall':
        width = float(spec['bar_width'])
        if not 0 < width <= 1:
            raise ValueError(f"spec['bar_width'] must be in (0, 1], got {width}.")
        spec['bar_width'] = width
        if not spec['bars']:
            raise ValueError("spec['bars'] must list at least one bar.")
        bars = []
        for index, raw_bar in enumerate(spec['bars']):
            where = f"spec['bars'][{index}]"
            bar = _fill(raw_bar, _WATERFALL_BAR_FIELDS, where)
            if bar['kind'] not in ('delta', 'total'):
                raise ValueError(f"{where}['kind'] must be 'delta' or 'total', got {bar['kind']!r}")
            texesc.validate(bar['label'], f"{where}['label']")
            bar['label'] = texesc.unescape_newlines(bar['label'])
            bars.append(bar)
        spec['bars'] = bars
        if spec['row_filter'] is not None and (not isinstance(spec['row_filter'], dict)):
            raise ValueError(f"spec['row_filter'] must be a {{column: value}} dict selecting exactly one row; got {spec['row_filter']!r}")
    elif chart_type == 'bar':
        width = float(spec['bar_width'])
        if not 0 < width <= 1:
            raise ValueError(f"spec['bar_width'] must be in (0, 1], got {width}.")
        spec['bar_width'] = width
        gap = float(spec['group_gap'])
        if not 0 <= gap < 1:
            raise ValueError(f"spec['group_gap'] is the blank fraction of a bar's width and must be in [0, 1); got {gap}.")
        spec['group_gap'] = gap
        spec['baseline'] = float(spec['baseline'])
        if spec['group_label'] is not None and spec['group'] is None:
            raise ValueError("spec['group_label'] names the column holding each group's legend text, but spec['group'] is not set, so there are no groups. Set 'group' too, or drop 'group_label'.")
        if spec['series_label'] is not None and spec['series'] is None:
            raise ValueError("spec['series_label'] names the column holding each stacked series' legend text, but spec['series'] is not set, so there is nothing stacked. Set 'series' too, or drop 'series_label'.")
        has_se = spec['se'] is not None
        has_bounds = spec['lower'] is not None or spec['upper'] is not None
        if has_se and has_bounds:
            raise ValueError("spec['se'] and spec['lower']/spec['upper'] are alternative ways to say the same thing; give one form, not both. 'se' is symmetric (+/- 1 SE); 'lower'/'upper' are explicit bounds.")
        if has_bounds and (spec['lower'] is None or spec['upper'] is None):
            missing = 'lower' if spec['lower'] is None else 'upper'
            raise ValueError(f"spec['{missing}'] is missing. Explicit error-bar bounds need BOTH 'lower' and 'upper'; use 'se' for a symmetric interval.")
        if spec['se_on'] not in ('total', 'segment'):
            raise ValueError(f"spec['se_on'] must be 'total' (one whisker at the bar's full height) or 'segment' (one per stacked segment); got {spec['se_on']!r}")
        if not (has_se or has_bounds) and 'se_on' in raw:
            raise ValueError("spec['se_on'] was set but no error-bar data was given; add 'se', or 'lower' and 'upper'.")
        if spec['colors'] is not None:
            if isinstance(spec['colors'], str):
                raise ValueError(f"spec['colors'] must be a LIST of colour tokens, one per group (or per series when there are no groups); got {spec['colors']!r}")
            spec['colors'] = list(spec['colors'])
            if not spec['colors']:
                raise ValueError("spec['colors'] must not be empty.")
    for field in _TEXT_FIELDS:
        value = spec[field]
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            spec[field] = [texesc.translate_glyphs(item) for item in value]
        else:
            spec[field] = texesc.translate_glyphs(value)
    texesc.validate_all({field: spec[field] for field in _TEXT_FIELDS})
    for field in _TEXT_FIELDS:
        value = spec[field]
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            spec[field] = [texesc.unescape_newlines(item) for item in value]
        else:
            spec[field] = texesc.unescape_newlines(value)
    _settings.finite(spec)
    return spec

def _fields(name):
    return {**globals()[name], **_settings.plain(_settings.value('spec_defaults').get(name, {}))}


def _escape_labels(raw):
    from copy import deepcopy
    result = deepcopy(raw)
    for key in ['xtitle','ytitle','xtitle_left','xtitle_right','key_title']:
        if key in result: result[key] = texesc.escape(result[key])
    for key in ['xtick_labels','ytick_labels']:
        if result.get(key) is not None: result[key] = [texesc.escape(v) for v in result[key]]
    for key in ['series','bars','bands','reference_lines']:
        entries = result.get(key)
        if isinstance(entries,list):
            for entry in entries:
                if isinstance(entry,dict) and 'label' in entry: entry['label'] = texesc.escape(entry['label'])
    if isinstance(result.get('legend'),dict) and result['legend'].get('labels') is not None:
        result['legend']['labels'] = [texesc.escape(v) for v in result['legend']['labels']]
    return result
