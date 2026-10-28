from ..diagnostics import trace as _log
from .. import settings as _settings
import re
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoLocator, FormatStrFormatter, MaxNLocator, ScalarFormatter
from .. import colors
from .. import style as _style, style
_TRAILING_ZEROS = re.compile('(\\d+\\.\\d*?)0+(?!\\d)')
_BARE_POINT = re.compile('(\\d+)\\.(?!\\d)')

class _TrimmedFormatter(ScalarFormatter):

    def __call__(self, value, pos=None):
        text = super().__call__(value, pos)
        return _BARE_POINT.sub('\\1', _TRAILING_ZEROS.sub('\\1', text))

def style_min_ticks(profile):
    
    return profile.tick_min_n

def apply_ticks(axis_obj, ticks, tick_labels, tick_format, axis_name, profile=None):
    if isinstance(ticks, dict):
        axis_obj.set_major_locator(MaxNLocator(nbins=ticks['count'] - 1, steps=[1, 2, 2.5, 5, 10]))
    elif ticks is not None:
        axis_obj.set_ticks(ticks)
        if tick_labels is not None:
            axis_obj.set_ticklabels(tick_labels)
    if profile is not None and isinstance(axis_obj.get_major_locator(), AutoLocator):
        axis_obj.set_major_locator(MaxNLocator(nbins=profile.tick_nbins, steps=[1, 2, 5, 10], min_n_ticks=style_min_ticks(profile)))
    if tick_format is not None:
        if tick_labels is not None:
            raise ValueError(f"spec['{axis_name}tick_format'] and spec['{axis_name}tick_labels'] both set; they conflict.")
        axis_obj.set_major_formatter(FormatStrFormatter(tick_format))
    elif tick_labels is None and isinstance(axis_obj.get_major_formatter(), ScalarFormatter):
        axis_obj.set_major_formatter(_TrimmedFormatter())

def apply_axes(ax, spec, profile):
    ax.set_ylabel(spec['ytitle'])
    xtitle = spec['xtitle'] if spec['xtitle'] else ''
    edge_left = spec.get('xtitle_left')
    edge_right = spec.get('xtitle_right')
    fixed_layout = getattr(profile, 'layout', None) is not None
    if (edge_left or edge_right) and (not fixed_layout):
        xtitle = ' \n \n' + xtitle
    ax.set_xlabel(xtitle)
    if edge_left or edge_right:
        for text, xpos, halign in ((edge_left, 0.0, 'left'), (edge_right, 1.0, 'right')):
            if not text:
                continue
            annotation = ax.annotate(text, xy=(xpos, 1.0), xycoords=('axes fraction', ax.xaxis.label), ha=halign, va='top', annotation_clip=False)
            annotation._twpgf_edge_align = halign
        _log(f'    [xedge ] edge-aligned x labels: {edge_left!r} flush to the y axis, {edge_right!r} flush to the end of the x axis')
    if spec['log_x']:
        ax.set_xscale('log')
    if spec['log_y']:
        ax.set_yscale('log')
    apply_extended_limits(ax, spec)
    apply_ticks(ax.xaxis, spec['xticks'], spec['xtick_labels'], spec['xtick_format'], 'x', profile)
    apply_ticks(ax.yaxis, spec['yticks'], spec['ytick_labels'], spec['ytick_format'], 'y', profile)
    if spec['xtick_rotation'] is not None:
        for label in ax.get_xticklabels():
            label.set_rotation(spec['xtick_rotation'])
            label.set_horizontalalignment('right')
    for label in ax.get_yticklabels():
        label.set_rotation(0)
    grid = _settings.value('grid')
    if spec['grid'] is None:
        axis = grid['chart_axis'].get(spec['type'], grid['axis'])
        ax.grid(False, axis='both')
        if grid['enabled'] and axis != 'none': ax.grid(True, axis=axis)
    if spec['grid'] is not None:
        if spec['grid'] == 'none':
            ax.grid(False)
        else:
            ax.grid(False)
            ax.grid(True, axis=spec['grid'])

def unclip_gridlines(ax):
    for gl in list(ax.get_xgridlines()) + list(ax.get_ygridlines()):
        gl.set_clip_on(False)

def apply_extended_limits(ax, spec):
    for field, getter, setter, name in (('xlim', ax.get_xlim, ax.set_xlim, 'x'), ('ylim', ax.get_ylim, ax.set_ylim, 'y')):
        requested = spec[field]
        if requested is None:
            continue
        data_low, data_high = getter()
        want_low, want_high = requested
        low = data_low if want_low is None else min(data_low, want_low)
        high = data_high if want_high is None else max(data_high, want_high)
        setter(low, high)
        pieces = []
        if want_low is not None and low < want_low - 1e-12:
            pieces.append(f"low held at the data's {low:g} (beyond {want_low:g})")
        elif want_low is not None:
            pieces.append(f'low extended to {low:g}')
        else:
            pieces.append(f'low from the data ({low:g})')
        if want_high is not None and high > want_high + 1e-12:
            pieces.append(f"high held at the data's {high:g} (beyond {want_high:g})")
        elif want_high is not None:
            pieces.append(f'high extended to {high:g}')
        else:
            pieces.append(f'high from the data ({high:g})')
        _log(f'    [{name}range] ' + '; '.join(pieces))
_GRIDLINE_COINCIDENCE = 1e-09

def _hide_coincident_gridlines(ax, spec):
    if not spec['reference_lines']:
        return
    for axis_name, axis, get_ticks in (('x', ax.xaxis, ax.get_xticks), ('y', ax.yaxis, ax.get_yticks)):
        positions = [line['at'] for line in spec['reference_lines'] if line['axis'] == axis_name]
        if not positions:
            continue
        low, high = ax.get_xlim() if axis_name == 'x' else ax.get_ylim()
        span = abs(high - low) or 1.0
        tolerance = _GRIDLINE_COINCIDENCE * span
        ticks = list(get_ticks())
        gridlines = axis.get_gridlines()
        for tick, gridline in zip(ticks, gridlines):
            if any((abs(tick - at) <= tolerance for at in positions)):
                gridline.set_visible(False)
                _log(f'    [grid  ] suppressed the {axis_name} gridline at {tick:g}: a reference line already marks it')

def apply_reference_lines(ax, spec, ink_scale):
    if not spec['reference_lines']:
        return
    for line in spec['reference_lines']:
        kwargs = {'color': colors.resolve(line['color']), 'linestyle': style.dash_for(line['pattern']), 'linewidth': style.linewidth_points(line['linewidth']) * ink_scale, 'zorder': _settings.constant('primitives.common', 'REFERENCE_LINE_ZORDER')}
        if line['label'] is not None:
            kwargs['label'] = line['label']
        if line['axis'] == 'x':
            ax.axvline(line['at'], **kwargs)
        else:
            ax.axhline(line['at'], **kwargs)
    _hide_coincident_gridlines(ax, spec)

def _row_major_to_column_major(entries, ncols):
    if ncols <= 1:
        return list(entries)
    nrows = int(np.ceil(len(entries) / ncols))
    grid = [entries[row * ncols:(row + 1) * ncols] for row in range(nrows)]
    out = []
    for col in range(ncols):
        for row in range(nrows):
            if col < len(grid[row]):
                out.append(grid[row][col])
    return out

def _blank_entry():
    return Line2D([], [], linestyle='none', marker='none', label=' ')

def _swatch_handle(handle, swatch_pt):
    from matplotlib.lines import Line2D
    if not isinstance(handle, Line2D):
        return handle
    dash = getattr(handle, '_dash_pattern', None)
    if not dash or not dash[1]:
        return handle
    period = sum(dash[1])
    if period <= 0:
        return handle
    cycles = max(1, int(-(-swatch_pt // period)))
    seq = list(dash[1]) * cycles
    seq[-1] = 1000.0
    proxy = Line2D([], [], color=handle.get_color(), linewidth=handle.get_linewidth(), alpha=handle.get_alpha(), marker=handle.get_marker(), markersize=handle.get_markersize(), markerfacecolor=handle.get_markerfacecolor(), markeredgecolor=handle.get_markeredgecolor())
    proxy.set_dashes(seq)
    proxy.set_dash_capstyle('butt')
    return proxy

def apply_legend(fig, ax, spec, profile, auto_labels_only=False):
    legend_spec = spec['legend']
    if legend_spec is not None and (not legend_spec['show'] or legend_spec['position'] == 'none'):
        return None
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return None
    if legend_spec is None and auto_labels_only and (len(handles) == 1):
        _log(f'    [legend] none drawn: one series, and no label was given for it -- the only text available is the column name {labels[0]!r}, which is not publication text. Pass labels() to get a legend, or legendcols()/legendorder() to force one.')
        return None
    if legend_spec is not None and legend_spec['labels'] is not None:
        if len(legend_spec['labels']) != len(handles):
            raise ValueError(f"spec['legend']['labels'] has {len(legend_spec['labels'])} entries but the plot produced {len(handles)} legend handles.")
        labels = list(legend_spec['labels'])
    entries = list(zip(handles, labels))
    swatch_pt = _style.legend_swatch_pt(profile.base_pt)
    entries = [(_swatch_handle(handle, swatch_pt), label) for handle, label in entries]
    if legend_spec is not None and legend_spec['order'] is not None:
        reordered = []
        for item in legend_spec['order']:
            if item in (None, '', 'blank'):
                reordered.append((_blank_entry(), ' '))
            else:
                index = int(item) - 1
                if not 0 <= index < len(entries):
                    raise ValueError(f"spec['legend']['order'] refers to series {item}, but the plot has {len(entries)} series. Use 'blank' for a spacer.")
                reordered.append(entries[index])
        entries = reordered
    ncols = _settings.value('legend')['columns']
    if legend_spec is not None and legend_spec['cols'] is not None:
        ncols = legend_spec['cols']
    cap = getattr(profile, 'legend_max_cols', None)
    if legend_spec is not None and legend_spec['position'] == 'separate':
        cap = None
    if cap is not None and ncols > cap:
        _log(f'    [legend] {ncols} columns requested, capped at {cap} for the {profile.name} profile -- {ncols} do not fit a {profile.width_in:.2f}in figure, and the .pgf clips what does not. The entries wrap onto more rows; none is dropped.')
        ncols = cap
    emphasis = spec.get('emphasis') if isinstance(spec, dict) else None
    explicit_order = legend_spec is not None and legend_spec['order'] is not None
    separate = legend_spec is not None and legend_spec['position'] == 'separate'
    if emphasis is not None and (not explicit_order) and (not separate) and (ncols > 1):
        position = None
        for i, entry in enumerate(spec['series']):
            if entry['y'] == emphasis:
                position = i
                break
        if position is not None and position < len(entries):
            promoted = [entries[position]]
            promoted += [(_blank_entry(), ' ')] * (ncols - 1)
            promoted += [e for i, e in enumerate(entries) if i != position]
            entries = promoted
            _log(f'    [legend] {emphasis!r} promoted to its own row ({ncols - 1} spacer(s) after it)')
    entries = _row_major_to_column_major(entries, ncols)
    position = 'outside lower center'
    kwargs = {}
    if legend_spec is not None and legend_spec['fontsize'] is not None:
        kwargs['fontsize'] = style.text_points(legend_spec['fontsize'])
        _log(f"    [legend] size {kwargs['fontsize']:.3f}pt ({legend_spec['fontsize']!r})")
    return fig.legend([handle for handle, _ in entries], [label for _, label in entries], loc=position, ncols=ncols, frameon=False, **kwargs)
