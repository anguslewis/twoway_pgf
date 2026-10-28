from ..diagnostics import trace as _log
from .. import settings as _settings
import matplotlib.transforms as mtransforms
import numpy as np
from .. import colors, style
from . import common
RELATIVE_SUM_TOLERANCE = 1e-06
BASELINE = 0.0

def _select_row(frame, row_filter):
    if row_filter is None:
        if len(frame) != 1:
            raise ValueError(f"the plot data has {len(frame)} rows and spec['row_filter'] is not set. A waterfall draws ONE panel; add a row_filter such as {{'panel': 'RoW', 'weighting': 'debt_weighted'}} to pick it.")
        return frame.iloc[0]
    mask = np.ones(len(frame), dtype=bool)
    for column, value in row_filter.items():
        if column not in frame.columns:
            raise KeyError(f"spec['row_filter'] key {column!r} is not a column of the plot data; columns are {list(frame.columns)}")
        mask &= frame[column].astype(str).to_numpy() == str(value)
    matched = frame[mask]
    if len(matched) != 1:
        raise ValueError(f"spec['row_filter'] {row_filter} matched {len(matched)} rows; it must match exactly one. Available combinations:\n" + frame[list(row_filter)].drop_duplicates().to_string(index=False))
    return matched.iloc[0]

def build(fig, ax, frame, spec, profile):
    connector_pt = style.linewidth_points(_settings.constant('primitives.waterfall', 'CONNECTOR_WIDTH')) * profile.ink_scale
    row = _select_row(frame, spec['row_filter'])
    if spec['row_filter']:
        _log(f"    [panel ] row_filter {spec['row_filter']} -> 1 row")
    bars = spec['bars']
    for bar in bars:
        if bar['value_col'] not in frame.columns:
            raise KeyError(f"bar {bar['label']!r} reads column {bar['value_col']!r}, which is not in the plot data; columns are {list(frame.columns)}")
        if bar['sd_col'] is not None and bar['sd_col'] not in frame.columns:
            raise KeyError(f"bar {bar['label']!r} reads sd column {bar['sd_col']!r}, which is not in the plot data; columns are {list(frame.columns)}")
    values = [float(row[bar['value_col']]) for bar in bars]
    kinds = [bar['kind'] for bar in bars]
    sds = [float(row[bar['sd_col']]) if bar['sd_col'] is not None else 0.0 for bar in bars]
    if not np.isfinite(values).all() or not np.isfinite(sds).all() or any(sd < 0 for sd in sds):
        raise ValueError('waterfall values and SDs must be finite; SDs must be nonnegative')
    delta_sum = sum((v for v, k in zip(values, kinds) if k == 'delta'))
    if not np.isfinite(delta_sum): raise ValueError('waterfall delta sum overflow')
    totals = [v for v, k in zip(values, kinds) if k == 'total']
    if totals:
        for total in totals:
            error = abs(delta_sum - total)
            tolerance = max(spec['sum_check_tolerance'], RELATIVE_SUM_TOLERANCE * abs(total))
            if error > tolerance:
                raise ValueError(f'waterfall does not add up: the delta bars sum to {delta_sum!r} but the total bar is {total!r} (difference {error:.3e}, tolerance {tolerance:.3e}). Either a bar column is wrong or the decomposition itself is not additive -- fix the data, not the tolerance. If the data came through `import delimited` in Stata, check it was read as double and not float (`set type double`).')
        _log(f'    [check ] delta bars sum to {delta_sum:.12g}, total bar {totals[0]:.12g}, difference {abs(delta_sum - totals[0]):.3e} -- OK')
    else:
        _log("    [check ] no 'total' bar in this waterfall; sum identity not checked")
    positions = np.arange(len(bars), dtype=float)
    running = 0.0
    geometry = []
    for value, kind in zip(values, kinds):
        if kind == 'delta':
            bottom = running
            running += value
            top = running
        else:
            bottom = 0.0
            top = value
        if not np.isfinite([bottom, top]).all(): raise ValueError('waterfall cumulative sum overflow')
        geometry.append({'bottom': bottom, 'top': top, 'value': value, 'kind': kind})
    width = spec['bar_width']
    for index, (position, bar, geom) in enumerate(zip(positions, bars, geometry)):
        if geom['kind'] == 'total':
            nominal = colors.resolve(spec['total_color'])
        elif geom['value'] >= 0:
            nominal = colors.resolve(spec['up_color'])
        else:
            nominal = colors.resolve(spec['down_color'])
        fill = colors.intensity(nominal, _settings.constant('colors', 'BAR_INTENSITY'))
        container = ax.bar(position, geom['top'] - geom['bottom'], bottom=geom['bottom'], width=width, facecolor=fill, edgecolor='none', linewidth=0.0, zorder=2.0)
        geom['patch'] = container[0]
        geom['color'] = fill
        geom['nominal_color'] = nominal
        _log(f"    [bar   ] {bar['label']!r:34s} {geom['value']:+9.4f} ({geom['bottom']:+.4f} -> {geom['top']:+.4f})  fill {fill} (solid; {nominal} at intensity {_settings.constant('colors', 'BAR_INTENSITY'):g}, as Stata bars)")
        if bar['sd_col'] is not None:
            sd = float(row[bar['sd_col']])
            whisker = colors.lighten(fill, _settings.constant('primitives.waterfall', 'SD_WHISKER_LIGHTEN'))
            centre = geom['top']
            low, high = (centre - sd, centre + sd)
            truncated_low = low < BASELINE
            truncated_high = high < BASELINE
            if truncated_low:
                low = BASELINE
            if truncated_high:
                high = BASELINE
            whisker_pt = style.linewidth_points(_settings.constant('primitives.waterfall', 'SD_WHISKER_WIDTH')) * profile.ink_scale
            ax.plot([position, position], [low, high], color=whisker, linewidth=whisker_pt, solid_capstyle='butt', zorder=2.4)
            half_cap = _settings.constant('primitives.waterfall', 'SD_CAP_WIDTH') / 2.0
            for value, is_truncated in ((low, truncated_low), (high, truncated_high)):
                if is_truncated:
                    continue
                ax.plot([position - half_cap, position + half_cap], [value, value], color=whisker, linewidth=whisker_pt, solid_capstyle='butt', zorder=2.4)
            note = ''
            if truncated_low or truncated_high:
                note = f"  TRUNCATED at {BASELINE:g} ({('lower' if truncated_low else 'upper')} end uncapped, so it does not read as a real bound)"
            _log(f"    [sd    ] {bar['label']!r}: +/- {sd:.4f}  [{low:+.4f}, {high:+.4f}]  whisker {whisker} at {whisker_pt:.3f}pt{note}")
    nudges = []
    if spec['connectors']:
        tol = 1e-09
        for index in range(len(bars) - 1):
            left, right = (geometry[index], geometry[index + 1])
            left_end = left['top']
            right_start = right['top'] if right['kind'] == 'total' else right['bottom']
            band_top = max(left_end, right_start)
            band_bottom = min(left_end, right_start)

            def _above(g, level):
                lo, hi = (min(g['bottom'], g['top']), max(g['bottom'], g['top']))
                return (lo + hi) / 2.0 > level
            level = band_top
            left_above = _above(left, level)
            right_above = _above(right, level)
            into_total = right['kind'] == 'total'
            descends = left['top'] < left['bottom'] - tol
            if into_total and left_above != right_above:
                offset_pt, side = (-connector_pt / 2.0, 'down')
                why = "into the TOTAL: band lowered and the incoming bar extended, so the total's level stays exact"
                nudges.append((left, 'end_across', index))
            elif descends:
                offset_pt, side = (+connector_pt / 2.0, 'up')
                why = 'the left bar descends, so the level is its bottom edge'
            else:
                offset_pt, side = (-connector_pt / 2.0, 'down')
                why = 'the left bar ascends, so the level is its top edge'
            if not into_total and left_above != right_above:
                nudges.append((right, 'start_across', index))
            x0 = positions[index] + width / 2
            x1 = positions[index + 1] - width / 2
            if abs(band_top - band_bottom) > tol:
                ax.bar((x0 + x1) / 2.0, band_top - band_bottom, bottom=band_bottom, width=x1 - x0, facecolor=colors.resolve(_settings.constant('primitives.waterfall', 'CONNECTOR_COLOR')), edgecolor='none', linewidth=0.0, zorder=_settings.constant('primitives.waterfall', 'CONNECTOR_ZORDER'))
            else:
                ax.plot([x0, x1], [band_top, band_top], color=colors.resolve(_settings.constant('primitives.waterfall', 'CONNECTOR_COLOR')), linewidth=connector_pt, linestyle='solid', solid_capstyle='butt', zorder=_settings.constant('primitives.waterfall', 'CONNECTOR_ZORDER'), transform=mtransforms.offset_copy(ax.transData, fig=fig, y=offset_pt, units='points'))
            _log(f"    [conn  ] {bars[index]['label']!r} -> {bars[index + 1]['label']!r}: left_end {left_end:+.4f}, right_start {right_start:+.4f} -> band [{band_bottom:+.4f}, {band_top:+.4f}], {connector_pt:.3f}pt {side} -- {why}")
            if abs(band_top - band_bottom) > tol:
                _log(f'    [conn  ] NB those two levels DISAGREE by {abs(band_top - band_bottom):.4f}; the rectangle spans the gap so it is visible rather than hidden.')
    _log('    [label ] none -- bar values are quoted in the text, not printed')
    ax.set_xticks(positions)
    ax.set_xticklabels([bar['label'] for bar in bars])
    ax.set_xlim(-0.5 - (1 - width) / 2, len(bars) - 0.5 + (1 - width) / 2)
    if any(sds):
        extents = [g['top'] for g in geometry] + [g['bottom'] for g in geometry]
        whisker_high = max((g['top'] + sd for g, sd in zip(geometry, sds)))
        whisker_low = min((max(g['top'] - sd, BASELINE) for g, sd in zip(geometry, sds)))
        data_high, data_low = (max(extents), min(min(extents), BASELINE))
        span = max(whisker_high, data_high) - min(whisker_low, data_low) or 1.0
        pad = _settings.constant('primitives.waterfall', 'WHISKER_PAD_FRACTION') * span
        new_high = max(whisker_high + pad, data_high)
        new_low = min(whisker_low - pad, data_low) if whisker_low < data_low else data_low
        ax.set_ylim(new_low, new_high)
        _log(f'    [axis  ] y limits {new_low:+.4f} to {new_high:+.4f} (padded by {pad:.4f} so the whisker caps are not clipped)')
    common.apply_axes(ax, spec, profile)

    low, high = ax.get_ylim()
    if low < 0 < high:
        ax.axhline(0.0, color=_settings.constant('colors', 'AXISLINE'), linewidth=style.linewidth_points(_settings.value('strokes')['waterfall_zero']) * profile.ink_scale, linestyle='solid', zorder=_settings.constant('primitives.waterfall', 'ZERO_LINE_ZORDER'))
    common.apply_reference_lines(ax, spec, ink_scale=profile.ink_scale)
    common.apply_legend(fig, ax, spec, profile)
    if nudges:
        fig.canvas.draw()
        y_lo, y_hi = ax.get_ylim()
        axes_pt = ax.get_position().height * fig.get_figheight() * 72.0
        t_data = connector_pt * (y_hi - y_lo) / axes_pt
        for geom, how, index in nudges:
            patch = geom['patch']
            y, height = (patch.get_y(), patch.get_height())
            if how == 'start_across':
                if height > 0:
                    patch.set_y(y - t_data)
                    patch.set_height(height + t_data)
                    moved = 'start (bottom) down'
                else:
                    patch.set_y(y + t_data)
                    patch.set_height(height - t_data)
                    moved = 'start (top) up'
            else:
                patch.set_height(height - t_data)
                moved = 'end down, to keep the total exact'
            _log(f"    [flush ] {bars[index]['label']!r} -> {bars[index + 1]['label']!r}: {moved} by {connector_pt:.3f}pt ({t_data:.5f} data units)")
    return geometry
