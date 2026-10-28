from .diagnostics import trace as _log
from . import settings as _settings
import numpy as np
DEVIATION_TOLERANCE_PT = 0.25
SAMPLES_PER_COLUMN = 8
RDP_TOLERANCE_PX = 0.5
REFERENCE_DPI = 300.0
PLOT_REGION_W_FRACTION = 436.7317 / 504.0
PLOT_REGION_H_FRACTION = 210.7981 / 324.0

def plot_columns(width_in):
    return max(1, int(round(width_in * PLOT_REGION_W_FRACTION * REFERENCE_DPI)))

def plot_rows(height_in):
    return max(1, int(round(height_in * PLOT_REGION_H_FRACTION * REFERENCE_DPI)))

def default_max_points(width_in):
    return SAMPLES_PER_COLUMN * plot_columns(width_in)
DEFAULT_METHOD = {'line': 'envelope_rdp', 'scatter': 'density', 'waterfall': 'none'}
METHODS = ('none', 'uniform', 'minmax', 'lttb', 'envelope_rdp', 'density')
COLLINEAR_MIN_POINTS = 200
COLLINEAR_MIN_VERTICES = 60
COLLINEAR_TOLERANCE_PX = 1e-06
FLAT_FLOOR_FRACTION = 0.005

def _resolve_limits(values, limit):
    lo = limit[0] if limit is not None and limit[0] is not None else None
    hi = limit[1] if limit is not None and limit[1] is not None else None
    if lo is None:
        lo = float(np.nanmin(values))
    if hi is None:
        hi = float(np.nanmax(values))
    return (float(lo), float(hi))

def count_shape_points(x, y, width_in, height_in, xlim=None, ylim=None):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3:
        return len(x)
    x_lo, x_hi = _resolve_limits(x, xlim)
    y_lo, y_hi = _resolve_limits(y, ylim)
    x_span = (x_hi - x_lo) or 1.0
    y_span = (y_hi - y_lo) or 1.0
    x_px = (x - x_lo) / x_span * plot_columns(width_in)
    y_px = (y - y_lo) / y_span * plot_rows(height_in)
    return int(len(_rdp_indices(x_px, y_px, COLLINEAR_TOLERANCE_PX)))

def collinearity_warning(x, y, label, width_in, height_in, xlim=None, ylim=None):
    if len(x) < COLLINEAR_MIN_POINTS:
        return None
    y_arr = np.asarray(y, dtype=float)
    span = float(np.nanmax(y_arr) - np.nanmin(y_arr))
    if span <= 0:
        return None
    support = y_arr - np.nanmin(y_arr) > FLAT_FLOOR_FRACTION * span
    if int(np.count_nonzero(support)) < COLLINEAR_MIN_POINTS:
        return None
    vertices = count_shape_points(np.asarray(x, dtype=float)[support], y_arr[support], width_in, height_in, xlim, ylim)
    if vertices >= COLLINEAR_MIN_VERTICES:
        return None
    return f"    [reduce] WARNING {label!r}: {len(x)} points but only {vertices} carry the curve's shape -- the runs between them are collinear, so this plots as a {vertices - 1}-segment polyline however many points it carries.\n    [reduce]          If this series is a DENSITY, its source is probably a linear interpolation. Stata's `kdens' is one common cause: it estimates on an internal grid spanning the whole data range and interpolates linearly to the points you ask for, so a long-tailed variable leaves few knots inside a narrow plotted window. Pass `exact' (or a large `n()') to kdens.\n    [reduce]          If it is a step or piecewise-linear series, this is expected and can be ignored."

def _finite_runs(x, y):
    finite = np.isfinite(y) & np.isfinite(x)
    runs = []
    start = None
    for index, ok in enumerate(finite):
        if ok and start is None:
            start = index
        elif not ok and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(y)))
    return runs

def _lttb_indices(x, y, n_out):
    n_in = len(x)
    if n_out >= n_in:
        return np.arange(n_in)
    if n_out < 3:
        return np.array([0, n_in - 1])
    edges = np.linspace(1, n_in - 1, n_out - 1).astype(int)
    kept = [0]
    for bucket in range(n_out - 2):
        lo, hi = (edges[bucket], edges[bucket + 1])
        next_lo, next_hi = (edges[bucket + 1], edges[bucket + 2] if bucket + 2 < len(edges) else n_in)
        if hi <= lo:
            continue
        if next_hi > next_lo:
            next_x = x[next_lo:next_hi].mean()
            next_y = y[next_lo:next_hi].mean()
        else:
            next_x, next_y = (x[-1], y[-1])
        prev_x, prev_y = (x[kept[-1]], y[kept[-1]])
        areas = np.abs((prev_x - next_x) * (y[lo:hi] - prev_y) - (prev_x - x[lo:hi]) * (next_y - prev_y))
        kept.append(lo + int(np.argmax(areas)))
    kept.append(n_in - 1)
    return np.array(kept)

def _minmax_indices(n_in, n_out):
    if n_out >= n_in:
        return np.arange(n_in)
    n_buckets = max(1, n_out // 2)
    edges = np.linspace(0, n_in, n_buckets + 1).astype(int)
    return (edges, n_buckets)

def _column_envelope_indices(x, y, n_columns):
    x_lo, x_hi = (float(x.min()), float(x.max()))
    if x_hi <= x_lo:
        return np.array([0, len(x) - 1])
    column = np.clip(((x - x_lo) / (x_hi - x_lo) * n_columns).astype(np.int64), 0, n_columns - 1)
    order = np.argsort(column, kind='stable')
    cols = column[order]
    boundaries = np.flatnonzero(np.diff(cols)) + 1
    last = len(x) - 1
    kept = set()
    for group in np.split(order, boundaries):
        ys = y[group]
        low = int(group[int(np.argmin(ys))])
        high = int(group[int(np.argmax(ys))])
        kept.update((low, high))
        kept.update((int(group[int(np.argmin(x[group]))]) for _ in (0,)))
        kept.add(int(group[int(np.argmax(x[group]))]))
        for extreme in (low, high):
            if extreme > 0:
                kept.add(extreme - 1)
            if extreme < last:
                kept.add(extreme + 1)
    return np.array(sorted(kept))

def _rdp_indices(x_px, y_px, tolerance):
    n = len(x_px)
    if n < 3:
        return np.arange(n)
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        segment = slice(start + 1, end)
        run = x_px[end] - x_px[start]
        if run == 0:
            distance = np.abs(y_px[segment] - y_px[start])
        else:
            slope = (y_px[end] - y_px[start]) / run
            chord = y_px[start] + slope * (x_px[segment] - x_px[start])
            distance = np.abs(y_px[segment] - chord)
        if distance.size == 0:
            continue
        worst = int(np.argmax(distance))
        if distance[worst] > tolerance:
            split = start + 1 + worst
            keep[split] = True
            stack.append((start, split))
            stack.append((split, end))
    return np.flatnonzero(keep)

def _envelope_rdp_indices(x, y, n_columns, width_in, height_in, xlim, ylim):
    stage1 = _column_envelope_indices(x, y, n_columns)
    if len(stage1) < 3:
        return stage1
    x_lo = xlim[0] if xlim is not None else float(x.min())
    x_hi = xlim[1] if xlim is not None else float(x.max())
    y_lo = ylim[0] if ylim is not None else float(y.min())
    y_hi = ylim[1] if ylim is not None else float(y.max())
    x_span = x_hi - x_lo or 1.0
    y_span = y_hi - y_lo or 1.0
    rows = height_in * PLOT_REGION_H_FRACTION * REFERENCE_DPI
    x_px = (x[stage1] - x_lo) / x_span * n_columns
    y_px = (y[stage1] - y_lo) / y_span * rows
    stage2 = _rdp_indices(x_px, y_px, RDP_TOLERANCE_PX)
    return stage1[stage2]

def _reduce_run(x, y, n_out, method, geometry):
    if method == 'envelope_rdp':
        return _envelope_rdp_indices(x, y, plot_columns(geometry['width_in']), geometry['width_in'], geometry['height_in'], geometry['xlim'], geometry['ylim'])
    if method == 'uniform':
        if n_out >= len(x):
            return np.arange(len(x))
        step = np.linspace(0, len(x) - 1, n_out).astype(int)
        return np.unique(step)
    if method == 'minmax':
        if n_out >= len(x):
            return np.arange(len(x))
        edges, n_buckets = _minmax_indices(len(x), n_out)
        kept = {0, len(x) - 1}
        for bucket in range(n_buckets):
            lo, hi = (edges[bucket], edges[bucket + 1])
            if hi <= lo:
                continue
            kept.add(lo + int(np.argmin(y[lo:hi])))
            kept.add(lo + int(np.argmax(y[lo:hi])))
        return np.array(sorted(kept))
    if method == 'lttb':
        return _lttb_indices(x, y, n_out)
    raise ValueError(f'unknown line reduction method {method!r}; known: {METHODS}')

def reduce_line(x, y, max_points=None, method='envelope_rdp', label='', width_in=6.5, height_in=4.178571, xlim=None, ylim=None):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.shape != y.shape:
        raise ValueError(f'x and y differ in shape: {x.shape} vs {y.shape}')
    if method not in METHODS:
        raise ValueError(f'unknown line reduction method {method!r}; known: {METHODS}')
    if method == 'none':
        return (x, y, {'applied': False, 'reason': 'method=none', 'n_in': len(x), 'n_out': len(x)})
    if max_points is None:
        max_points = default_max_points(width_in)
    geometry = {'width_in': width_in, 'height_in': height_in, 'xlim': xlim, 'ylim': ylim}
    runs = _finite_runs(x, y)
    n_finite = sum((hi - lo for lo, hi in runs))
    n_bad_x = int(np.sum(~np.isfinite(x)))
    if n_bad_x:
        _log(f'    [reduce] NOTE: {n_bad_x} of {len(x)} rows have a non-finite x and are treated as gaps in the line. Check the plot data if that was not intended.')
    if n_finite <= max_points:
        return (x, y, {'applied': False, 'reason': f'{n_finite} finite points already <= cap {max_points}', 'n_in': len(x), 'n_out': len(x), 'method': method})
    if any(bounds is not None and None in bounds for bounds in (xlim, ylim)):
        raise ValueError('line reduction requires two finite axis bounds or no bounds; '
                         'supply both bounds, or set reduce=False to use open bounds')
    out_x, out_y, kept_total = ([], [], 0)
    for position, (lo, hi) in enumerate(runs):
        run_x, run_y = (x[lo:hi], y[lo:hi])
        share = max(2 * SAMPLES_PER_COLUMN, int(round(max_points * (hi - lo) / n_finite)))
        idx = _reduce_run(run_x, run_y, share, method, geometry)
        kept_total += len(idx)
        if position > 0:
            out_x.append(np.array([np.nan]))
            out_y.append(np.array([np.nan]))
        out_x.append(run_x[idx])
        out_y.append(run_y[idx])
    reduced_x = np.concatenate(out_x)
    reduced_y = np.concatenate(out_y)
    return (reduced_x, reduced_y, {'applied': True, 'method': method, 'n_in': len(x), 'n_out': len(reduced_x), 'n_finite_in': n_finite, 'n_finite_out': kept_total, 'n_runs': len(runs), 'cap': max_points, 'label': label})

def reduce_scatter(x, y, max_points, method='density', label='', cells=None, seed=0):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if method == 'none':
        return (x, y, {'applied': False, 'reason': 'method=none', 'n_in': len(x), 'n_out': len(x)})
    if method != 'density':
        raise ValueError(f"unknown scatter reduction method {method!r}; only 'density' and 'none'")
    finite = np.isfinite(x) & np.isfinite(y)
    if finite.sum() <= max_points:
        return (x, y, {'applied': False, 'reason': f'{int(finite.sum())} finite points already <= cap {max_points}', 'n_in': len(x), 'n_out': len(x)})
    x_f, y_f = (x[finite], y[finite])
    if cells is None:
        cells = max(20, int(np.sqrt(max_points) * 4))

    def bin_at(resolution):
        x_bin = np.clip(((x_f - x_f.min()) / max(np.ptp(x_f), 1e-300) * resolution).astype(int), 0, resolution - 1)
        y_bin = np.clip(((y_f - y_f.min()) / max(np.ptp(y_f), 1e-300) * resolution).astype(int), 0, resolution - 1)
        ids = x_bin.astype(np.int64) * resolution + y_bin
        order = np.argsort(ids, kind='stable')
        boundaries = np.flatnonzero(np.diff(ids[order])) + 1
        return np.split(order, boundaries)
    groups = bin_at(cells)
    while len(groups) > max_points and cells > 4:
        cells = max(4, cells // 2)
        groups = bin_at(cells)
    per_cell = max(1, int(max_points // len(groups)))
    rng = np.random.default_rng(seed)
    keep = []
    for group in groups:
        if len(group) <= per_cell:
            keep.append(group)
        else:
            keep.append(rng.choice(group, size=per_cell, replace=False))
    keep = np.concatenate(keep)
    extremes = [int(np.argmin(x_f)), int(np.argmax(x_f)), int(np.argmin(y_f)), int(np.argmax(y_f))]
    keep = np.unique(np.concatenate([keep, np.array(extremes)]))
    keep_sorted = np.sort(keep)
    return (x_f[keep_sorted], y_f[keep_sorted], {'applied': True, 'method': method, 'n_in': len(x), 'n_out': len(keep_sorted), 'cap': max_points, 'cells': cells, 'occupied_cells': len(groups), 'per_cell_cap': per_cell, 'label': label})

def deviation_points(x, y, x_reduced, y_reduced, width_in, height_in, xlim, ylim):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    xs, ys = (x[finite], y[finite])
    if xs.size < 2:
        return 0.0
    if np.any(np.diff(xs) < 0):
        raise ValueError("deviation_points needs non-decreasing x (it interpolates along x). This series is non-monotone, so the guard cannot be evaluated; pass reduce={'enabled': False} or reduce the series yourself.")
    finite_r = np.isfinite(x_reduced) & np.isfinite(y_reduced)
    xr, yr = (np.asarray(x_reduced)[finite_r], np.asarray(y_reduced)[finite_r])
    if xr.size < 2:
        return float('inf')
    interpolated = np.interp(xs, xr, yr)
    y_span = ylim[1] - ylim[0] if ylim is not None else float(np.ptp(ys))
    if y_span <= 0:
        return 0.0
    plot_height_pt = height_in * 72.0 * PLOT_REGION_H_FRACTION
    n_columns = plot_columns(width_in)
    x_lo = xlim[0] if xlim is not None else float(xs.min())
    x_hi = xlim[1] if xlim is not None else float(xs.max())
    if x_hi <= x_lo:
        return 0.0
    column = np.clip(((xs - x_lo) / (x_hi - x_lo) * n_columns).astype(np.int64), 0, n_columns - 1)
    order = np.argsort(column, kind='stable')
    cols = column[order]
    orig = ys[order]
    red = interpolated[order]
    boundaries = np.flatnonzero(np.diff(cols)) + 1
    worst = 0.0
    for group in np.split(np.arange(cols.size), boundaries):
        o_lo, o_hi = (orig[group].min(), orig[group].max())
        r_lo, r_hi = (red[group].min(), red[group].max())
        worst = max(worst, abs(o_lo - r_lo), abs(o_hi - r_hi))
    return float(worst / y_span * plot_height_pt)

def assert_visually_identical(x, y, x_reduced, y_reduced, width_in, height_in, xlim, ylim, tolerance_pt=DEVIATION_TOLERANCE_PT, label=''):
    deviation = deviation_points(x, y, x_reduced, y_reduced, width_in, height_in, xlim, ylim)
    if deviation > tolerance_pt:
        raise ValueError(f"data reduction of series {label!r} moved the curve by {deviation:.4f}pt on the printed page, over the {tolerance_pt}pt tolerance -- the reduction would be VISIBLE. Raise max_points, switch method to 'minmax' (which preserves the envelope exactly), or disable reduction for this series.")
    return deviation
