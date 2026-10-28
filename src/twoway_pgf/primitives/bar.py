from ..diagnostics import trace as _log
from .. import settings as _settings
import numpy as np
from .. import colors, style
from . import common

def _require_columns(frame, spec):
    wanted = {key: spec[key] for key in ('category', 'value', 'category_label', 'group', 'group_label', 'series', 'series_label', 'se', 'lower', 'upper') if spec[key] is not None}
    missing = {key: col for key, col in wanted.items() if col not in frame.columns}
    if missing:
        raise KeyError('bar spec names column(s) that are not in the plot data: ' + ', '.join((f'{key}={col!r}' for key, col in sorted(missing.items()))) + f'. Columns present: {list(frame.columns)}')
    return wanted

def _ordered_levels(frame, column):
    values = frame[column].to_numpy()
    return sorted(set(values.tolist()))

def _unique_label(frame, mask, label_column, what):
    labels = sorted(set(frame.loc[mask, label_column].tolist()))
    if len(labels) != 1:
        raise ValueError(f'{what} carries {len(labels)} different {label_column!r} values ({labels}); that selection must name exactly one label.')
    return _unescape_label(str(labels[0]))

def _label_for(frame, key_column, key, label_column):
    if label_column is None:
        return f'{key}'
    return _unique_label(frame, frame[key_column] == key, label_column, f'{key_column}={key!r}')

def _unescape_label(text):
    from .. import texesc
    return texesc.unescape_newlines(text)

def _bar_positions(n_categories, n_groups, bar_width, group_gap):
    slot = bar_width / n_groups
    drawn = slot * (1.0 - group_gap)
    centres = np.empty((n_categories, n_groups), dtype=float)
    for index in range(n_categories):
        left = index - bar_width / 2.0
        for g in range(n_groups):
            centres[index, g] = left + slot * (g + 0.5)
    return (centres, drawn)

def _group_base_color(spec, index):
    if spec['colors'] is not None:
        tokens = spec['colors']
        if index >= len(tokens):
            raise ValueError(f"spec['colors'] has {len(tokens)} entries but the data needs at least {index + 1}. Give one colour per group (or per series when there are no groups).")
        return colors.resolve(tokens[index])
    return colors.series_color(index)

def _assert_opaque(ax):
    offenders = []
    for patch in ax.patches:
        alpha = patch.get_alpha()
        if alpha is not None and alpha < 1.0:
            offenders.append(f'patch alpha={alpha}')
        face = patch.get_facecolor()
        if len(face) == 4 and face[3] < 1.0:
            offenders.append(f'patch facecolor alpha={face[3]}')
    if offenders:
        raise ValueError('bar segments must be fully OPAQUE, but ' + '; '.join(offenders) + '. Stacked segments are separated by fading toward white (colors.BAR_STACK_FADE), never by transparency.')

def _read_error(frame, spec, mask, top):
    if spec['se'] is not None:
        values = frame.loc[mask, spec['se']].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return None
        if values.size > 1 and (not np.allclose(values, values[0])):
            raise ValueError(f"a single bar carries {values.size} different {spec['se']!r} values ({values.tolist()}); with se_on='total' the SE must be one number per bar. Use se_on='segment' for a per-segment interval.")
        se = float(values[0])
        if se < 0:
            raise ValueError(f"{spec['se']!r} must be >= 0, got {se}.")
        return (top - se, top + se)
    if spec['lower'] is None:
        return None
    lows = frame.loc[mask, spec['lower']].to_numpy(dtype=float)
    highs = frame.loc[mask, spec['upper']].to_numpy(dtype=float)
    finite = np.isfinite(lows) & np.isfinite(highs)
    if not finite.any():
        return None
    lows, highs = (lows[finite], highs[finite])
    for name, values in ((spec['lower'], lows), (spec['upper'], highs)):
        if values.size > 1 and (not np.allclose(values, values[0])):
            raise ValueError(f"a single bar carries {values.size} different {name!r} values ({values.tolist()}); with se_on='total' the bounds describe the whole bar, so they must agree across its rows. Use se_on='segment' for a per-segment interval.")
    low, high = (float(lows[0]), float(highs[0]))
    if high < low:
        raise ValueError(f"{spec['upper']!r} ({high}) is below {spec['lower']!r} ({low}) on a bar.")
    return (low, high)

def build(fig, ax, frame, spec, profile):
    _require_columns(frame, spec)
    categories = _ordered_levels(frame, spec['category'])
    groups = _ordered_levels(frame, spec['group']) if spec['group'] else [None]
    series = _ordered_levels(frame, spec['series']) if spec['series'] else [None]
    _log(f'    [shape ] {len(categories)} categories x {len(groups)} group(s) x {len(series)} stacked series = {len(categories) * len(groups) * len(series)} segment(s) expected, {len(frame)} row(s) supplied')
    centres, drawn_width = _bar_positions(len(categories), len(groups), spec['bar_width'], spec['group_gap'])
    _log(f"    [layout] bar width {drawn_width:.4f} of a unit category slot (bar_width {spec['bar_width']:g} / {len(groups)} group(s), group_gap {spec['group_gap']:g})")
    legend_done = set()
    tops = {}
    error_ends = []
    for ci, category in enumerate(categories):
        in_category = frame[spec['category']] == category
        for gi, group in enumerate(groups):
            in_group = in_category
            if group is not None:
                in_group = in_group & (frame[spec['group']] == group)
            base = _group_base_color(spec, gi)
            bottom = spec['baseline']
            for si, series_level in enumerate(series):
                rows = in_group
                if series_level is not None:
                    rows = rows & (frame[spec['series']] == series_level)
                heights = frame.loc[rows, spec['value']].to_numpy(dtype=float)
                if heights.size == 0:
                    raise ValueError(f"no row for {spec['category']}={category!r}" + (f", {spec['group']}={group!r}" if group is not None else '') + (f", {spec['series']}={series_level!r}" if series_level is not None else '') + '. A long bar table must be complete: give an explicit zero rather than omitting the row, or the bar silently loses a segment.')
                if heights.size > 1:
                    raise ValueError(f"{heights.size} rows for one segment ({spec['category']}={category!r}" + (f", {spec['group']}={group!r}" if group is not None else '') + (f", {spec['series']}={series_level!r}" if series_level is not None else '') + f'): {heights.tolist()}. One row per drawn segment.')
                height = float(heights[0])
                if not np.isfinite(height):
                    raise ValueError(f"{spec['value']!r} is not finite for {spec['category']}={category!r} (got {height}); a missing segment height would silently shorten the bar.")
                fill = colors.bar_fill(base, depth=si)
                key = (gi, si)
                label = None
                if key not in legend_done:
                    label = _legend_label(frame, spec, rows, group, series_level)
                    legend_done.add(key)
                ax.bar(centres[ci, gi], height, bottom=bottom, width=drawn_width, facecolor=fill, edgecolor='none', linewidth=0.0, zorder=_settings.constant('primitives.bar', 'BAR_ZORDER'), label=label)
                if ci == 0:
                    _log(f"    [fill  ] group {gi + 1} series {si + 1}: {fill} (depth {si}: {base} at intensity {_settings.constant('colors', 'BAR_INTENSITY'):g}" + (f" then {_settings.constant('colors', 'BAR_STACK_FADE'):g} x{si}" if si else '') + '), opaque')
                bottom += height
            tops[ci, gi] = bottom
            if spec['se_on'] == 'total':
                ends = _read_error(frame, spec, in_group, bottom)
                if ends is not None:
                    error_ends.append((centres[ci, gi], ends, base))
        if spec['se_on'] == 'segment':
            for gi, group in enumerate(groups):
                in_group = in_category
                if group is not None:
                    in_group = in_group & (frame[spec['group']] == group)
                base = _group_base_color(spec, gi)
                running = spec['baseline']
                for series_level in series:
                    rows = in_group
                    if series_level is not None:
                        rows = rows & (frame[spec['series']] == series_level)
                    running += float(frame.loc[rows, spec['value']].to_numpy(float)[0])
                    ends = _read_error(frame, spec, rows, running)
                    if ends is not None:
                        error_ends.append((centres[ci, gi], ends, base))
    error_pt = style.linewidth_points(_settings.value('strokes')['bar_error']) * profile.ink_scale
    for x, (low, high), base in error_ends:
        whisker = colors.lighten(colors.bar_fill(base), _settings.constant('primitives.bar', 'SE_WHISKER_LIGHTEN'))
        centre = (low + high) / 2.0
        ax.errorbar(x, centre, yerr=(high - low) / 2.0, fmt='none', color=colors.resolve(_settings.constant('primitives.bar', 'ERROR_MARKER_FACE_COLOR')), ecolor=whisker, elinewidth=error_pt, capsize=_settings.constant('primitives.bar', 'SE_CAPSIZE'), capthick=error_pt, zorder=_settings.constant('primitives.bar', 'WHISKER_ZORDER'))
    if error_ends:
        _log(f"    [se    ] {len(error_ends)} error bar(s), se_on={spec['se_on']!r}, whisker lightened {_settings.constant('primitives.bar', 'SE_WHISKER_LIGHTEN'):g} from each bar's fill")
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels([_label_for(frame, spec['category'], category, spec['category_label']) for category in categories])
    ax.set_xlim(-0.5, len(categories) - 0.5)
    ax.tick_params(axis='x', length=0)

    common.apply_axes(ax, spec, profile)
    if error_ends and spec['ylim'] is None:
        data_low, data_high = ax.get_ylim()
        whisker_high = max((high for _, (_, high), _ in error_ends))
        whisker_low = min((low for _, (low, _), _ in error_ends))
        span = max(whisker_high, data_high) - min(whisker_low, data_low) or 1.0
        pad = _settings.constant('primitives.bar', 'WHISKER_PAD_FRACTION') * span
        new_high = max(whisker_high + pad, data_high)
        new_low = min(whisker_low - pad, data_low) if whisker_low < data_low else data_low
        ax.set_ylim(new_low, new_high)
        _log(f'    [ylim  ] {new_low:.4f} .. {new_high:.4f} (padded by {pad:.4f} so the whisker caps are not clipped)')
    common.apply_reference_lines(ax, spec, ink_scale=profile.ink_scale)
    common.apply_legend(fig, ax, spec, profile)
    _assert_opaque(ax)
    _log(f'    [check ] all {len(ax.patches)} bar segment(s) fully opaque')
    return []

def _legend_label(frame, spec, mask, group, series_level):
    if series_level is not None and spec['series_label'] is not None:
        what = f"{spec['series']}={series_level!r}"
        if group is not None:
            what += f" x {spec['group']}={group!r}"
        return _unique_label(frame, mask, spec['series_label'], what)
    if group is not None and series_level is not None:
        group_text = _label_for(frame, spec['group'], group, spec['group_label']) if spec['group_label'] is not None else f'{group}'
        return f'{group_text} ({series_level})'
    if group is not None and spec['group_label'] is not None:
        return _label_for(frame, spec['group'], group, spec['group_label'])
    if series_level is not None:
        return f'{series_level}'
    if group is not None:
        return f'{group}'
    return None
