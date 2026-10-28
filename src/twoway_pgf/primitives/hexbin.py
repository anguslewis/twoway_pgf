from ..diagnostics import trace as _log
# Hexbin geometry adapted from Ben Jann hexplot/heatplot.
# MIT License
# 
# Copyright (c) 2019 benjann
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from .. import settings as _settings
import matplotlib
import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch
from .. import colors, layout, style
from . import common
_VERTEX_ANGLES = np.deg2rad(np.array([-90.0, -30.0, 30.0, 90.0, 150.0, 210.0]))
_ASPECT_TOLERANCE = 0.1

def _size_scale(counts, srange, hi, how):
    lo_a, hi_a = srange
    counts = np.asarray(counts, dtype=float)
    if how == 'linear':
        frac = counts / hi
    elif how == 'log':
        frac = np.log(np.clip(counts, 1.0, None)) / np.log(max(hi, 1.0 + 1e-09))
    elif how == 'log_radius':
        r_lo = np.sqrt(lo_a)
        pos = np.log(np.clip(counts, 1.0, None)) / np.log(max(hi, 1.0 + 1e-09))
        return r_lo + (np.sqrt(hi_a) - r_lo) * pos
    else:
        raise ValueError(f"spec['size_scale'] = {how!r}; expected 'linear', 'log' or 'log_radius'.")
    return np.sqrt(lo_a + (hi_a - lo_a) * frac)

def _categories(values, cuts):
    idx = np.searchsorted(np.asarray(cuts, dtype=float), values, side='right')
    return np.clip(idx, 0, len(cuts) - 1)

def _key_labels(cuts, max_count=None):
    edges = [1.0] + [float(c) for c in cuts]
    out = []
    for i, (lo, hi) in enumerate(zip(edges, edges[1:])):
        last = i == len(edges) - 2
        lo_txt = int(np.floor(lo))
        if last and max_count is not None and (max_count >= hi):
            out.append(f'{lo_txt:,}+')
            continue
        hi_txt = int(hi) if last else int(hi) - 1 if float(hi).is_integer() else int(np.floor(hi))
        out.append(f'{lo_txt:,}-{hi_txt:,}')
    return out

def _ramp(ends, n):
    if n < 2:
        raise ValueError('hexbin discrete color scale requires at least two cuts; supply two or more cuts, or use a log color scale.')
    if isinstance(ends, str):
        if ends != 'grey':
            raise ValueError(f"spec['ramp'] = {ends!r}; the only named ramp is 'grey'. Otherwise pass a pair of colour tokens.")
        greys = colors.grey_ramp(n)[::-1]
        return [tuple((int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))) for h in greys]
    lo, hi = (np.array([int(colors.resolve(e)[i:i + 2], 16) for i in (1, 3, 5)]) / 255.0 for e in ends)
    return [tuple(lo + (hi - lo) * (i / (n - 1))) for i in range(n)]

def _lattice_step(centres, label):
    uniq = np.unique(np.round(centres, 9))
    if uniq.size < 2:
        raise ValueError(f'hexbin requires at least two distinct occupied {label} cell centres, '
                         f'even with explicit dimensions; got {uniq.size}. Use scatter for sparse points or rebin upstream.')
    return float(np.diff(uniq).min())

def bin_observations(x, y, nbins, half_w=None, half_h=None, x0=None, y0=None):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = (x[finite], y[finite])
    if x.size == 0:
        raise ValueError('no finite observations to bin')
    nbins = float(nbins)
    if not np.isfinite(nbins) or nbins <= 0 or nbins != int(nbins):
        raise ValueError('hexbin bins must be a finite positive integer')
    if half_h is None:
        span = max(y.max() - y.min(), x.max() - x.min())
        if not np.isfinite(span) or span <= 0:
            raise ValueError('hexbin observations need a finite positive coordinate span; use scatter for identical points')
        half_h = span / (1.5 * nbins)
    if half_w is None:
        half_w = np.cos(np.pi / 6) * half_h
    if not np.isfinite(half_h) or not np.isfinite(half_w) or half_h <= 0 or half_w <= 0:
        raise ValueError('hexbin half-height and half-width must be finite and positive')
    if x0 is None:
        x0 = x.min()
    if y0 is None:
        y0 = y.min()
    c30 = np.cos(np.pi / 6)
    u, v = (x * c30 / half_w, y / half_h)
    u0, v0 = (x0 * c30 / half_w, y0 / half_h)
    best_d = np.full(x.shape, np.inf)
    best_i = np.zeros(x.shape, dtype=np.int64)
    best_j = np.zeros(x.shape, dtype=np.int64)
    for parity in (0, 1):
        j = np.round((v - v0 - parity * 1.5) / 3.0) * 2 + parity
        cu = u0 + j % 2 * c30
        i = np.round((u - cu) / (2 * c30))
        du = u - (cu + i * 2 * c30)
        dv = v - (v0 + j * 1.5)
        d = du * du + dv * dv
        take = d < best_d
        best_d = np.where(take, d, best_d)
        best_i = np.where(take, i.astype(np.int64), best_i)
        best_j = np.where(take, j.astype(np.int64), best_j)
    keys, counts = np.unique(np.column_stack((best_i, best_j)), axis=0, return_counts=True)
    ii, jj = (keys[:, 0], keys[:, 1])
    cx = (u0 + jj % 2 * c30 + ii * 2 * c30) * half_w / c30
    cy = (v0 + jj * 1.5) * half_h
    return (cx, cy, counts.astype(float))

def _region_box(spec, layout):
    return layout.region_w_in, layout.region_h_in

def _page_ratio(spec, profile, ax):
    layout = profile.layout
    if layout is None:
        return 1.0
    box_w, box_h = _region_box(spec, layout)

    def span(field, getter):
        limits = spec.get(field)
        if limits and limits[0] is not None and (limits[1] is not None):
            return float(limits[1]) - float(limits[0])
        lo, hi = getter()
        return float(hi) - float(lo)
    dx = span('xlim', ax.get_xlim)
    dy = span('ylim', ax.get_ylim)
    return box_h / box_w * (dx / dy)

def build(fig, ax, frame, spec, profile):
    needed = ['x', 'y'] if spec['bins'] is not None else ['x', 'y', 'value']
    for key in needed:
        if spec[key] not in frame.columns:
            raise KeyError(f'spec[{key!r}] = {spec[key]!r} is not a column of the plot data; columns are {list(frame.columns)}')
    if spec['bins'] is not None:
        cx, cy, counts = bin_observations(frame[spec['x']].to_numpy(dtype=float), frame[spec['y']].to_numpy(dtype=float), spec['bins'])
        _log(f"    [hexbin] binned {len(frame)} observations into {cx.size} cells at bins({spec['bins']})")
    else:
        if spec['value'] is None:
            raise ValueError("spec['value'] is required when spec['bins'] is not set: without bins the data is one row per PRE-BINNED cell and 'value' names its count column.")
        cx = frame[spec['x']].to_numpy(dtype=float)
        cy = frame[spec['y']].to_numpy(dtype=float)
        counts = frame[spec['value']].to_numpy(dtype=float)
    keep = np.isfinite(cx) & np.isfinite(cy) & np.isfinite(counts) & (counts >= 1)
    dropped = int((~keep).sum())
    cx, cy, counts = (cx[keep], cy[keep], counts[keep])
    if cx.size == 0:
        raise ValueError('no hexbin cells with a count of 1 or more; nothing to draw')
    _log(f'    [hexbin] {cx.size} occupied cells, counts {counts.min():.0f}-{counts.max():.0f}' + (f'; {dropped} row(s) dropped as empty or non-finite' if dropped else ''))
    lat_h = _lattice_step(cy, 'y') / 1.5
    lat_w = _lattice_step(cx, 'x')
    half_h = spec['hex_half_height']
    half_w = spec['hex_half_width']
    if half_h is None or half_w is None:
        if spec['hex_shape'] == 'regular':
            ratio = np.cos(np.pi / 6) * _page_ratio(spec, profile, ax)
            half_h = min(lat_h, lat_w / ratio)
            half_w = ratio * half_h
        else:
            half_h, half_w = (lat_h, lat_w)
    _log(f'    [hexbin] lattice cell half-height {lat_h:.6f}, half-width {lat_w:.6f}')
    _log(f'    [hexbin] drawn  cell half-height {half_h:.6f} ({half_h / lat_h:.3f}x), half-width {half_w:.6f} ({half_w / lat_w:.3f}x)' + ('  OVERLAPS its lattice cell' if half_w > lat_w + 1e-12 or half_h > lat_h + 1e-12 else ''))
    if spec['sizeprop']:
        lo, hi = spec['srange']
        scale = _size_scale(counts, spec['srange'], counts.max(), spec['size_scale'])
        _log(f"    [hexbin] sizeprop on, srange {lo}-{hi} as AREA, {spec['size_scale']} in the count -> linear scale {scale.min():.4f}-{scale.max():.4f}")
    else:
        scale = np.ones_like(counts)
        _log('    [hexbin] sizeprop off -- every cell drawn at full size')
    verts = [np.column_stack((x + half_w * scale[i] * np.cos(_VERTEX_ANGLES) / np.cos(np.pi / 6), y + half_h * scale[i] * np.sin(_VERTEX_ANGLES))) for i, (x, y) in enumerate(zip(cx, cy))]
    continuous = spec['color_scale'] == 'log'
    if continuous:
        lo, hi = (1.0, float(counts.max()))
        if hi <= lo:
            raise ValueError('log hexbin color scale needs a count greater than one; use cuts for constant unit counts')
        frac = np.log(np.clip(counts, lo, hi) / lo) / np.log(hi / lo)
        shades = _ramp(spec['ramp'], _settings.constant('primitives.hexbin', '_RAMP_STEPS'))
        cell_colors = [shades[int(round(f * (_settings.constant('primitives.hexbin', '_RAMP_STEPS') - 1)))] for f in frac]
        _log(f'    [hexbin] continuous LOG colour over counts {lo:.0f}-{hi:.0f}')
        cuts = None
    else:
        cuts = spec['cuts']
        if cuts is None:
            raise ValueError("spec['cuts'] is required unless color_scale is 'log': discrete colour needs its breakpoints.")
        shades = _ramp(spec['ramp'], len(cuts))
        cat = _categories(counts, cuts)
        cell_colors = [shades[c] for c in cat]
        _log(f'    [hexbin] {len(cuts)} cut categories, occupied {cat.min() + 1}-{cat.max() + 1}')
    ax.add_collection(PolyCollection(verts, facecolors=cell_colors, edgecolors='none', linewidths=0.0, zorder=2))
    all_v = np.concatenate(verts)
    ax.set_xlim(float(all_v[:, 0].min()), float(all_v[:, 0].max()))
    ax.set_ylim(float(all_v[:, 1].min()), float(all_v[:, 1].max()))
    _log(f'    [hexbin] cell extent x [{all_v[:, 0].min():.3f}, {all_v[:, 0].max():.3f}]  y [{all_v[:, 1].min():.3f}, {all_v[:, 1].max():.3f}]')
    common.apply_axes(ax, spec, profile)
    common.apply_extended_limits(ax, spec)
    common.apply_reference_lines(ax, spec, ink_scale=profile.ink_scale)
    layout = profile.layout
    if layout is not None:
        region_w, region_h = _region_box(spec, layout)
        box = region_w / region_h
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        data = (x1 - x0) / (y1 - y0)
        want = np.cos(np.pi / 6) / (half_w / half_h) / data
        got = box / data
        _log(f'    [hexbin] axes box {box:.3f}:1 over a {data:.3f}:1 data range; regular cells want box/data = {want:.3f}, got {got:.3f}')
        if abs(got - want) / want > _ASPECT_TOLERANCE:
            _log(f"    [hexbin] WARNING cells will render {('wide and flat' if got > want else 'tall and thin')} by a factor of {got / want:.2f}. Set aspect() to about {want * data:.3f} for regular hexagons.")
    if spec['legend'] is None or spec['legend'].get('show', True):
        if continuous:
            _ramp_key(fig, ax, spec, profile, shades, counts, half_h, half_w)
        else:
            _legend(fig, ax, spec, profile, shades, _key_labels(cuts, max_count=float(counts.max())))
    return {'cells': int(cx.size), 'half_h': half_h, 'half_w': half_w, 'categories': None if cuts is None else len(cuts), 'color_scale': spec['color_scale'], 'max_count': float(counts.max())}

def _key_values(lo, hi, ticks, spec):
    mode = spec['key_mode']
    if mode == 'continuous':
        fr = np.linspace(0.0, 1.0, spec['key_steps'])
        return lo * (hi / lo) ** fr
    if mode == 'ticks':
        return np.array([float(t) for t in ticks])
    if mode == 'substeps':
        n_sub = int(spec['key_substeps'])
        if n_sub < 1:
            raise ValueError("spec['key_substeps'] must be at least 1")
        vals = []
        for a, b in zip(ticks, ticks[1:]):
            for k in range(n_sub):
                vals.append(float(a) * (float(b) / float(a)) ** (k / n_sub))
        vals.append(float(ticks[-1]))
        return np.array(vals)
    raise ValueError(f"spec['key_mode'] = {mode!r}; expected 'continuous', 'substeps' or 'ticks'.")

def _ramp_key(fig, ax, spec, profile, shades, counts, half_h, half_w):
    lo, hi = (1.0, float(counts.max()))
    ticks = spec['key_ticks']
    if ticks is None:
        decades = [10 ** k for k in range(0, int(np.ceil(np.log10(hi))) + 1)]
        ticks = [t for t in decades if lo <= t <= hi]
        if not ticks or ticks[-1] < hi * 0.6:
            ticks = ticks + [int(round(hi))]
    ticks = [t for t in ticks if lo <= t <= hi]
    layout = profile.layout
    if layout is not None:
        box_w_in, box_h_in = _region_box(spec, layout)
    else:
        box_w_in, box_h_in = (profile.width_in, profile.height_in)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()

    def _sc(count):
        if not spec['sizeprop']:
            return 1.0
        return float(_size_scale([count], spec['srange'], hi, spec['size_scale'])[0])

    def phys_half_h(count):
        return half_h * _sc(count) / (y1 - y0) * box_h_in

    def phys_half_w(count):
        return half_w * _sc(count) / (x1 - x0) * box_w_in
    vals = _key_values(lo, hi, ticks, spec)
    span_frac = _settings.constant('primitives.hexbin', 'KEY_SPAN_FRAC')
    bar_h_in = span_frac * box_h_in
    title_h_in = 0.0
    if spec['key_title']:
        probe = ax.text(0.0, 0.0, spec['key_title'], fontsize=profile.base_pt, alpha=0.0)
        fig.canvas.draw()
        title_h_in = probe.get_window_extent(renderer=fig.canvas.get_renderer()).height / fig.dpi
        probe.remove()
    pad_in = _settings.constant('primitives.hexbin', 'KEY_TITLE_PAD') * bar_h_in if spec['key_title'] else 0.0
    label_overhang_in = (_settings.constant('rowstack', 'CAP_RATIO') + _settings.constant('rowstack', 'FONT_BOX_DESCENT_RATIO')) / 2.0 * profile.base_pt
    group_h_in = label_overhang_in + bar_h_in + pad_in + title_h_in
    frac_lo = ((box_h_in - group_h_in) / 2.0 + label_overhang_in) / box_h_in
    _log(f'    [hexbin] key group centred: label {label_overhang_in:.3f} + bar {bar_h_in:.3f} + pad {pad_in:.3f} + title {title_h_in:.3f} = {group_h_in:.3f}in in a {box_h_in:.3f}in panel')
    pad_w_in = phys_half_w(hi) * 0.45
    key_w_in = 2.0 * phys_half_w(hi) + pad_w_in
    span_ln = np.log(hi / lo)
    pad_lo_ln = pad_hi_ln = 0.0
    for _ in range(3):
        total_ln = span_ln + pad_lo_ln + pad_hi_ln
        pad_lo_ln = phys_half_h(lo) / (span_frac * box_h_in) * total_ln
        pad_hi_ln = phys_half_h(hi) / (span_frac * box_h_in) * total_ln
    total_ln = span_ln + pad_lo_ln + pad_hi_ln
    tick_half_in = 0.0
    if spec['key_show_ticks']:
        tick_half_in = matplotlib.rcParams['ytick.major.size'] * _settings.constant('primitives.hexbin', '_KEY_TICK_LONGER') / 2.0 / 72.0
    gap = (_settings.constant('primitives.hexbin', 'KEY_GAP_IN') + tick_half_in) / box_w_in
    width = key_w_in / box_w_in
    kax = ax.inset_axes([1.0 + gap, frac_lo, width, span_frac])
    kax.set_yscale('log')
    kax.set_ylim(lo * np.exp(-pad_lo_ln), hi * np.exp(pad_hi_ln))
    kax.set_xlim(-1.0, 1.0)
    for side in ('top', 'bottom', 'left', 'right'):
        kax.spines[side].set_visible(False)
    kax.set_xticks([])
    kax.set_facecolor('none')
    kax.yaxis.set_ticks_position('right')
    kax.yaxis.set_label_position('right')
    kax.set_yticks(list(ticks))
    kax.set_yticklabels([f'{int(t):,}' for t in ticks])
    kax.minorticks_off()
    if spec['key_show_ticks']:
        kax.yaxis.set_ticks_position('both')
        kax.tick_params(axis='y', which='both', color=matplotlib.rcParams['axes.edgecolor'], width=matplotlib.rcParams['axes.linewidth'], length=matplotlib.rcParams['ytick.major.size'] * _settings.constant('primitives.hexbin', '_KEY_TICK_LONGER') / 2.0, labelleft=False, labelright=True, pad=2.0)
    else:
        kax.tick_params(axis='y', which='both', length=0.0, pad=3.0)
    kax.grid(visible=False, which='both', axis='x')
    if spec['key_show_ticks']:
        kax.grid(visible=True, which='major', axis='y', color=matplotlib.rcParams['axes.edgecolor'], linewidth=matplotlib.rcParams['axes.linewidth'], linestyle='-', alpha=1.0)
    else:
        kax.grid(visible=False, which='both', axis='y')
    verts, cols = ([], [])
    for val in vals:
        hh_ln = phys_half_h(val) / bar_h_in * total_ln
        xh = phys_half_w(val) * 2.0 / key_w_in
        verts.append(np.column_stack((xh * np.cos(_VERTEX_ANGLES) / np.cos(np.pi / 6), val * np.exp(hh_ln * np.sin(_VERTEX_ANGLES)))))
        f = np.log(val / lo) / span_ln
        cols.append(shades[int(round(f * (len(shades) - 1)))])
    kax.add_collection(PolyCollection(verts, facecolors=cols, edgecolors='none', linewidths=0.0))
    if spec['key_title']:
        kax.text(-tick_half_in / key_w_in, 1.0 + _settings.constant('primitives.hexbin', 'KEY_TITLE_PAD'), spec['key_title'], transform=kax.transAxes, ha='left', va='bottom', multialignment='left', fontsize=profile.base_pt)
        _log(f"    [hexbin] key title {spec['key_title']!r} above the bar")
    _log(f"    [hexbin] key '{spec['key_mode']}': {len(vals)} marks over counts {lo:.0f}-{hi:.0f}, ticked at {[int(t) for t in ticks]}{('' if spec['key_show_ticks'] else ' (tick marks off)')}")
    _log(f"    [hexbin] key marks match the panel: half-height {phys_half_h(lo) * 72:.2f}-{phys_half_h(hi) * 72:.2f}pt, column {key_w_in:.3f}in wide, gap {_settings.constant('primitives.hexbin', 'KEY_GAP_IN'):.3f}in, spanning {span_frac:.2f} of the panel height")
    return kax

def _legend(fig, ax, spec, profile, shades, labels):
    handles = [Patch(facecolor=c, edgecolor='none', label=l) for c, l in zip(shades, labels)][::-1]
    leg = ax.legend(handles=handles, loc='center left', bbox_to_anchor=(1.02, 0.5), frameon=False, handlelength=style.legend_handlelength(profile.base_pt), labelspacing=spec['legend_labelspacing'], fontsize=profile.base_pt, borderaxespad=0.0)
    _log(f"    [hexbin] legend {len(handles)} keys, outside right, densest first, labelspacing {spec['legend_labelspacing']}")
    return leg
