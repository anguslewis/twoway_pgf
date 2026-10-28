from ..diagnostics import trace as _log
from .. import settings as _settings
import numpy as np
from matplotlib.lines import Line2D
from .. import colors, style
from . import common

def _series_style(entry, index, ink_scale=1.0):
    color = colors.resolve(entry['color']) if entry['color'] is not None else colors.line_color(index)
    symbol_name = entry['symbol'] if entry['symbol'] is not None else _settings.value('scatter')['symbol']
    marker, filled = style.symbol_marker(symbol_name)
    size = style.symbol_points(entry['size'] if entry['size'] is not None else _settings.constant('style', 'SYMBOLSIZE_DEFAULT'))
    if entry['edge_width'] is not None:
        edge_width = style.linewidth_points(entry['edge_width'])
    elif filled:
        edge_width = 0.0
    else:
        edge_width = style.linewidth_points(_settings.constant('style', 'SYMBOL_EDGE_WIDTH'))
    return {'color': color, 'marker': marker, 'filled': filled, 'size': size * ink_scale, 'edge_width': edge_width * ink_scale, 'symbol_name': symbol_name}

def _legend_handle(resolved, label):
    return Line2D([], [], linestyle='none', marker=resolved['marker'], markersize=resolved['size'], markerfacecolor=resolved['color'] if resolved['filled'] else 'none', markeredgecolor=resolved['color'], markeredgewidth=resolved['edge_width'] if resolved['edge_width'] > 0 else 0.0, alpha=None, label=label)

def _assert_opaque_markers(ax):
    for line in ax.get_lines():
        requested = getattr(line, '_twpgf_requested_alpha', None)
        actual = line.get_alpha()
        if actual is None:
            continue
        if requested is None or abs(float(actual) - float(requested)) > 1e-12:
            raise AssertionError(f'marker series {line.get_label()!r} is drawn at alpha {actual!r} but the spec asked for {requested!r}. Markers are opaque unless a series sets alpha explicitly.')

def build(fig, ax, frame, spec, profile):
    if spec['x'] not in frame.columns:
        raise KeyError(f"spec['x'] = {spec['x']!r} is not a column of the plot data; columns are {list(frame.columns)}")
    total_markers = 0
    for entry in spec['series']:
        x_column = entry['x'] if entry['x'] is not None else spec['x']
        if x_column not in frame.columns or entry['y'] not in frame.columns:
            continue
        finite = np.isfinite(frame[x_column].to_numpy(dtype=float)) & np.isfinite(frame[entry['y']].to_numpy(dtype=float))
        total_markers += int(finite.sum())
    if spec['rasterize'] is None:
        rasterize = total_markers > _settings.constant('primitives.scatter', 'RASTER_AUTO_THRESHOLD')
        why = f"automatic: {total_markers} markers {('>' if rasterize else '<=')} threshold {_settings.constant('primitives.scatter', 'RASTER_AUTO_THRESHOLD')}"
    else:
        rasterize = bool(spec['rasterize'])
        why = f"spec asked for rasterize={spec['rasterize']!r}"
    _log(f"    [raster] marker layer {('RASTERISED' if rasterize else 'vector')} ({why})")
    if rasterize:
        _log(f"    [raster] at {spec['raster_dpi']:g} dpi. Axes, ticks, labels, legend and title stay VECTOR and are still typeset by the document.")
    fig._twpgf_rasterized = rasterize
    fig._twpgf_raster_dpi = spec['raster_dpi']
    handles = []
    for index, entry in enumerate(spec['series']):
        if entry['y'] not in frame.columns:
            raise KeyError(f"spec['series'][{index}]['y'] = {entry['y']!r} is not a column of the plot data; columns are {list(frame.columns)}")
        x_column = entry['x'] if entry['x'] is not None else spec['x']
        if x_column not in frame.columns:
            raise KeyError(f"spec['series'][{index}]['x'] = {x_column!r} is not a column of the plot data; columns are {list(frame.columns)}")
        x = frame[x_column].to_numpy(dtype=float)
        y = frame[entry['y']].to_numpy(dtype=float)
        label = entry['label'] if entry['label'] is not None else entry['y']
        resolved = _series_style(entry, index, ink_scale=profile.ink_scale)
        finite = np.isfinite(x) & np.isfinite(y)
        dropped = int((~finite).sum())
        artist, = ax.plot(x[finite], y[finite], linestyle='none', marker=resolved['marker'], markersize=resolved['size'], markerfacecolor=resolved['color'] if resolved['filled'] else 'none', markeredgecolor=resolved['color'], markeredgewidth=resolved['edge_width'], alpha=entry['alpha'], label='_nolegend_')
        artist._twpgf_requested_alpha = entry['alpha']
        if rasterize:
            artist.set_rasterized(True)
        artist.set_clip_on(False)
        handles.append(_legend_handle(resolved, label))
        alpha_note = 'opaque' if entry['alpha'] is None else f"alpha {entry['alpha']:.2f}"
        edge_note = 'no edge' if resolved['edge_width'] == 0 else f"edge {resolved['edge_width']:.3f}pt"
        _log(f'    [series] {label!r}: {int(finite.sum())} pts' + (f' ({dropped} missing dropped)' if dropped else '') + f", {resolved['symbol_name']} {('filled' if resolved['filled'] else 'hollow')}, colour {resolved['color']}, size {resolved['size']:.3f}pt, {edge_note}, {alpha_note}")
        if not finite.any():
            _log(f"    [series] {label!r} has NO plottable points -- drawn as a legend-only series, which is the Stata 'filler' idiom")
    _fit_axis(ax, frame, spec, axis='x')
    _fit_axis(ax, frame, spec, axis='y')
    common.apply_axes(ax, spec, profile)
    common.apply_reference_lines(ax, spec, ink_scale=profile.ink_scale)
    _apply_legend(fig, ax, spec, profile, handles)
    _assert_opaque_markers(ax)
    _warn_clipped_markers(ax, spec, profile)
    return []

def _warn_clipped_markers(ax, spec, profile):
    radius_pt = 0.0
    for line in ax.get_lines():
        if line.get_xdata(orig=True) is not None and len(line.get_xdata()) > 0:
            radius_pt = max(radius_pt, float(line.get_markersize()) / 2.0)
    if radius_pt <= 0:
        return
    for axis_name, limits, span_in, explicit in (('x', ax.get_xlim(), profile.width_in, spec['xlim']), ('y', ax.get_ylim(), profile.height_in, spec['ylim'])):
        if explicit is not None:
            continue
        low, high = limits
        span = abs(high - low)
        if span == 0 or span_in <= 0:
            continue
        per_point = span / (span_in * 72.0)
        pad = radius_pt * per_point
        touching = []
        for line in ax.get_lines():
            data = line.get_xdata() if axis_name == 'x' else line.get_ydata()
            values = np.asarray(data, dtype=float)
            if values.size == 0:
                continue
            if values.min() <= low + pad or values.max() >= high - pad:
                touching.append(line.get_label())
        if touching:
            option = f'{axis_name}range()'
            _log(f"    [note  ] a marker sits within half its own width of the {axis_name} axis limit, so it is CLIPPED -- the scheme's plot region spans exactly the data.\n    [note  ] Stata behaves the same way; the paper's own scatters pad by hand (yscale(range(.5 10.5)) on 1..10 data). Pass {option} to add room.")
            break

def _fit_axis(ax, frame, spec, axis):
    values = []
    for entry in spec['series']:
        column = (entry['x'] if entry['x'] is not None else spec['x']) if axis == 'x' else entry['y']
        column_values = frame[column].to_numpy(dtype=float)
        values.append(column_values[np.isfinite(column_values)])
    if not values:
        return
    stacked = np.concatenate(values)
    if stacked.size == 0:
        return
    low, high = (float(stacked.min()), float(stacked.max()))
    if high > low:
        if axis == 'x':
            ax.set_xlim(low, high)
        else:
            ax.set_ylim(low, high)

def _apply_legend(fig, ax, spec, profile, handles):
    for handle in handles:
        ax.add_line(handle)
    auto_only = all((entry['label'] is None for entry in spec['series']))
    return common.apply_legend(fig, ax, spec, profile, auto_labels_only=auto_only)
