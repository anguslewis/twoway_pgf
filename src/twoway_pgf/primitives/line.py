from ..diagnostics import trace as _log
from .. import settings as _settings
import numpy as np
from matplotlib.patheffects import AbstractPathEffect
from matplotlib.path import Path
from matplotlib.transforms import IdentityTransform
from .. import colors, reduce, style
from . import common

def default_styles(n_series, emphasis_index=None):
    plain = [i for i in range(n_series) if i != emphasis_index]
    n_plain = len(plain)
    colours = [None] * n_series
    patterns = [None] * n_series
    if emphasis_index is not None:
        colours[emphasis_index] = _settings.value('line_defaults')['emphasis_color']
        patterns[emphasis_index] = _settings.value('line_defaults')['emphasis_pattern']
    if n_plain > _settings.value('line_defaults')['grayscale_more_than']:
        ramp = colors.grey_ramp(n_plain, reserve_black=emphasis_index is not None)
        for slot, i in enumerate(plain):
            colours[i] = ramp[slot]
            patterns[i] = 'solid'
    else:
        for slot, i in enumerate(plain):
            colours[i] = colors.line_color(slot)
            patterns[i] = style.pattern_for_index(slot, n_plain)
    return (colours, patterns)

def _series_style(entry, index, default_color, default_pattern, ink_scale=1.0):
    color = colors.resolve(entry['color']) if entry['color'] is not None else colors.resolve(default_color)
    pattern = entry['pattern'] if entry['pattern'] is not None else default_pattern
    width = style.linewidth_points(entry['linewidth']) if entry['linewidth'] is not None else style.linewidth_points(_settings.value('strokes')['data'])
    return (color, style.dash_for(pattern), width * ink_scale, pattern)

class _TrimEnd(AbstractPathEffect):

    def __init__(self, points, at_end=True):
        super().__init__()
        self._points = points
        self._at_end = at_end

    def draw_path(self, renderer, gc, tpath, affine, rgbFace=None):
        vertices = affine.transform_path(tpath).vertices
        trimmed = self._shorten(np.asarray(vertices, dtype=float), self._points * renderer.dpi / 72.0)
        renderer.draw_path(gc, Path(trimmed), IdentityTransform(), rgbFace)

    def _shorten(self, v, distance):
        if len(v) < 2 or distance <= 0:
            return v
        if not self._at_end:
            v = v[::-1]
        tip = v[-1]
        keep = len(v) - 1
        while keep > 0 and np.hypot(*v[keep - 1] - tip) <= distance:
            keep -= 1
        if keep == 0:
            return v[:1] if self._at_end else v[:1][::-1]
        anchor = v[keep - 1]
        span = np.hypot(*anchor - tip)
        new_tip = tip + (anchor - tip) * (distance / span)
        out = np.vstack([v[:keep], new_tip])
        return out if self._at_end else out[::-1]

def _step_geometry(x, y, jumps, closed, label):
    n = len(x)
    if not jumps:
        raise ValueError(f"step() is on but series {label!r} declares no jumps. Each series needs jumps(...) -- the locations are the caller's, because a jump is not reliably distinguishable from a steep smooth stretch.")
    index = []
    for want in jumps:
        i = int(np.argmin(np.abs(x - float(want))))
        if i == 0:
            raise ValueError(f'series {label!r}: jump at {want} lands on the first sample (x = {x[0]}), so there is no branch before it to break.')
        index.append(i)
    index = sorted(set(index))
    bounds = [0] + index + [n]
    segments, closed_pts, open_pts = ([], [], [])
    for k in range(len(bounds) - 1):
        lo, hi = (bounds[k], bounds[k + 1])
        seg_x, seg_y = (list(x[lo:hi]), list(y[lo:hi]))
        if hi < n:
            jump_x = float(x[hi])
            if hi - lo >= 2:
                run = x[hi - 1] - x[hi - 2]
                slope = (y[hi - 1] - y[hi - 2]) / run if run else 0.0
                limit = float(y[hi - 1] + slope * (jump_x - x[hi - 1]))
            else:
                limit = float(y[hi - 1])
            seg_x.append(jump_x)
            seg_y.append(limit)
            arrival = float(y[hi])
            if closed == 'right':
                closed_pts.append((jump_x, arrival))
                open_pts.append((jump_x, limit))
            else:
                closed_pts.append((jump_x, limit))
                open_pts.append((jump_x, arrival))
        segments.append((np.asarray(seg_x), np.asarray(seg_y)))
    return (segments, closed_pts, open_pts)

def _draw_marks(ax, points, color, alpha, width, filled):
    if not points:
        return
    px = [p[0] for p in points]
    py = [p[1] for p in points]
    if filled:
        ax.plot(px, py, linestyle='none', marker='o', markersize=_settings.constant('primitives.line', '_MARK_OUTER_LW') * width, color=color, markeredgewidth=0, alpha=alpha, zorder=_settings.constant('primitives.line', '_MARK_ZORDER'), label='_nolegend_')
    else:
        ax.plot(px, py, linestyle='none', marker='o', markersize=_settings.constant('primitives.line', '_MARK_RING_LW') * width, markerfacecolor='none', markeredgecolor=color, markeredgewidth=width, alpha=alpha, zorder=_settings.constant('primitives.line', '_MARK_ZORDER'), label='_nolegend_')

def _reduce_options(spec, entry, profile):
    settings = entry['reduce'] or spec['reduce'] or {}
    enabled = settings.get('enabled', True)
    if spec.get('step'):
        enabled = False
    max_points = settings.get('max_points') or profile.max_points
    method = settings.get('method') or reduce.DEFAULT_METHOD['line']
    return (enabled, max_points, method)

def build(fig, ax, frame, spec, profile):
    if spec['x'] not in frame.columns:
        raise KeyError(f"spec['x'] = {spec['x']!r} is not a column of the plot data; columns are {list(frame.columns)}")
    x_full = frame[spec['x']].to_numpy(dtype=float)
    reports = []
    emphasis_index = None
    if spec['emphasis'] is not None:
        wanted = spec['emphasis']
        for i, entry in enumerate(spec['series']):
            if entry['y'] == wanted:
                emphasis_index = i
                break
        if emphasis_index is None:
            raise ValueError(f"spec['emphasis'] = {wanted!r} is not one of the plotted series; the y columns are {[e['y'] for e in spec['series']]}. emphasis() restyles and promotes an EXISTING series, it does not add one.")
    default_colours, default_patterns = default_styles(len(spec['series']), emphasis_index)
    if emphasis_index is not None:
        _log(f"    [emphasis] {spec['series'][emphasis_index]['y']!r}: black, solid, its own legend row")
    for index, entry in enumerate(spec['series']):
        if entry['y'] not in frame.columns:
            raise KeyError(f"spec['series'][{index}]['y'] = {entry['y']!r} is not a column of the plot data; columns are {list(frame.columns)}")
        y_full = frame[entry['y']].to_numpy(dtype=float)
        label = entry['label'] if entry['label'] is not None else entry['y']
        enabled, max_points, method = _reduce_options(spec, entry, profile)
        if enabled:
            x_plot, y_plot, report = reduce.reduce_line(x_full, y_full, max_points, method=method, label=label, width_in=profile.width_in, height_in=profile.height_in, xlim=spec['xlim'], ylim=spec['ylim'])
            if report['applied']:
                deviation = reduce.assert_visually_identical(x_full, y_full, x_plot, y_plot, profile.width_in, profile.height_in, spec['xlim'], spec['ylim'], label=label)
                report['deviation_pt'] = deviation
                _log(f"    [reduce] {label!r}: {report['n_in']} -> {report['n_out']} pts via {method}, max visual deviation {deviation:.4f} pt (tolerance {reduce.DEVIATION_TOLERANCE_PT} pt)")
            else:
                _log(f"    [reduce] {label!r}: no reduction -- {report['reason']}")
        else:
            x_plot, y_plot = (x_full, y_full)
            why = 'step mode' if spec['step'] else 'disabled by spec'
            report = {'applied': False, 'reason': why, 'n_in': len(x_full)}
            _log(f'    [reduce] {label!r}: OFF ({why}), plotting all {len(x_full)} pts')
            cap = reduce.default_max_points(profile.width_in)
            if len(x_full) > cap:
                _log(f'    [reduce] WARNING {label!r}: reduction is off and {len(x_full)} pts is over the {cap}-pt geometry cap; this series alone will add about {len(x_full) * 52 / 1000000.0:.1f} MB of TeX source. Drop noreduce, or set reduce(max_points) deliberately.')
        if not spec['step']:
            collinear = reduce.collinearity_warning(x_plot, y_plot, label, profile.width_in, profile.height_in, spec['xlim'], spec['ylim'])
            if collinear:
                _log(collinear)
        reports.append(report)
        color, dashes, width, pattern_name = _series_style(entry, index, default_colours[index], default_patterns[index], ink_scale=profile.ink_scale)
        if spec['step']:
            joint = spec['step_joint']
            segments, closed_pts, open_pts = _step_geometry(x_plot, y_plot, entry['jumps'], spec['step'], label)
            if joint == 'vertical':
                ax.plot(np.concatenate([s[0] for s in segments]), np.concatenate([s[1] for s in segments]), color=color, linestyle=dashes, linewidth=width, alpha=entry['alpha'], label=label)
            else:
                trim = _settings.constant('primitives.line', '_MARK_OUTER_LW') / 2.0 * width
                for slot, (seg_x, seg_y) in enumerate(segments):
                    if spec['step'] == 'right':
                        open_end = (slot < len(segments) - 1, True)
                    else:
                        open_end = (slot > 0, False)
                    ax.plot(seg_x, seg_y, color=color, linestyle=dashes, linewidth=width, alpha=entry['alpha'], label=label if slot == 0 else '_nolegend_', path_effects=[_TrimEnd(trim, at_end=open_end[1])] if open_end[0] else None)
                _draw_marks(ax, closed_pts, color, entry['alpha'], width, True)
                _draw_marks(ax, open_pts, color, entry['alpha'], width, False)
        else:
            ax.plot(x_plot, y_plot, color=color, linestyle=dashes, linewidth=width, marker=entry['marker'] if entry['marker'] else 'none', alpha=entry['alpha'], label=label)
        alpha_note = '' if entry['alpha'] is None else f", alpha {entry['alpha']:.2f}"
        _log(f'    [series] {label!r}: colour {color}, pattern {pattern_name}, width {width:.3f} pt{alpha_note}')
        if spec['step']:
            _log(f"    [step  ] {label!r}: {len(segments)} pieces, {len(closed_pts)} jump(s) at {', '.join((f'{p[0]:g}' for p in closed_pts))}; " + (f"{spec['step']}-closed, marks {_settings.constant('primitives.line', '_MARK_OUTER_LW') * width:.2f} pt across" if joint != 'vertical' else 'joined by vertical segments'))
    if spec['bands']:
        for index, band in enumerate(spec['bands']):
            for column in (band['lo'], band['hi']):
                if column not in frame.columns:
                    raise KeyError(f"spec['bands'][{index}] references column {column!r}, which is not in the plot data; columns are {list(frame.columns)}")
            ax.fill_between(x_full, frame[band['lo']].to_numpy(dtype=float), frame[band['hi']].to_numpy(dtype=float), color=colors.resolve(band['color']) if band['color'] else _settings.constant('colors', 'CI_AREA'), alpha=band['alpha'] if band['alpha'] is not None else _settings.constant('colors', 'CI_AREA_ALPHA'), linewidth=0, label=band['label'], zorder=1.2)
            _log(f"    [band  ] {band['lo']}..{band['hi']}")
    finite = np.isfinite(x_full)
    if finite.any():
        low, high = (float(x_full[finite].min()), float(x_full[finite].max()))
        if high > low:
            ax.set_xlim(low, high)
    common.apply_axes(ax, spec, profile)
    common.apply_reference_lines(ax, spec, ink_scale=profile.ink_scale)
    auto_only = all((entry['label'] is None for entry in spec['series']))
    common.apply_legend(fig, ax, spec, profile, auto_labels_only=auto_only)
    return reports
