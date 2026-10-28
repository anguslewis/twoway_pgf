from . import settings as _settings
import matplotlib

def symbol_points(name_or_points, short_side_pt=None):
    if short_side_pt is None:
        short_side_pt = _settings.constant('style', 'REFERENCE_SHORT_SIDE_PT')
    if not isinstance(name_or_points, str):
        return float(name_or_points)
    if name_or_points not in _settings.constant('style', 'STATA_SYMBOLSIZE_RELSIZE'):
        raise ValueError(f"unknown Stata msize style {name_or_points!r}; known: {sorted(_settings.constant('style', 'STATA_SYMBOLSIZE_RELSIZE'))}")
    return relsize_to_points(_settings.constant('style', 'STATA_SYMBOLSIZE_RELSIZE')[name_or_points], short_side_pt)

def symbol_marker(name):
    if name not in _settings.constant('style', 'STATA_SYMBOL_MARKER'):
        raise ValueError(f"unknown Stata msymbol style {name!r}; known: {sorted(_settings.constant('style', 'STATA_SYMBOL_MARKER'))}")
    return _settings.constant('style', 'STATA_SYMBOL_MARKER')[name]

def relsize_to_points(relsize, short_side_pt=None):
    if short_side_pt is None:
        short_side_pt = _settings.constant('style', 'REFERENCE_SHORT_SIDE_PT')
    return relsize / 100.0 * short_side_pt

def linewidth_points(name_or_points, short_side_pt=None):
    if short_side_pt is None:
        short_side_pt = _settings.constant('style', 'REFERENCE_SHORT_SIDE_PT')
    if not isinstance(name_or_points, str):
        return float(name_or_points)
    if name_or_points not in _settings.constant('style', 'STATA_LINEWIDTH_RELSIZE'):
        raise ValueError(f"unknown Stata linewidth style {name_or_points!r}; known: {sorted(_settings.constant('style', 'STATA_LINEWIDTH_RELSIZE'))}")
    return relsize_to_points(_settings.constant('style', 'STATA_LINEWIDTH_RELSIZE')[name_or_points], short_side_pt)

def textsize_points(name, short_side_pt=None):
    if short_side_pt is None:
        short_side_pt = _settings.constant('style', 'REFERENCE_SHORT_SIDE_PT')
    if name not in _settings.constant('style', 'STATA_TEXTSIZE_RELSIZE'):
        raise ValueError(f"unknown Stata gsize style {name!r}; known: {sorted(_settings.constant('style', 'STATA_TEXTSIZE_RELSIZE'))}")
    return relsize_to_points(_settings.constant('style', 'STATA_TEXTSIZE_RELSIZE')[name], short_side_pt)

def text_points(value, short_side_pt=None):
    if short_side_pt is None:
        short_side_pt = _settings.constant('style', 'REFERENCE_SHORT_SIDE_PT')
    if isinstance(value, str):
        return textsize_points(value, short_side_pt)
    points = float(value)
    if points <= 0:
        raise ValueError(f'a text size must be > 0 points, got {points}.')
    return points

def dash_for(pattern, short_side_pt=None):
    if short_side_pt is None:
        short_side_pt = _settings.constant('style', 'REFERENCE_SHORT_SIDE_PT')
    if pattern in (None, 'solid'):
        return 'solid'
    if pattern == 'none':
        return (0, (0.0, 10.0))
    if pattern in _settings.constant('style', 'HOUSE_DASH_SQUARES'):
        return (0, tuple((v * _settings.constant('style', 'SQUARE_PT') for v in _settings.constant('style', 'HOUSE_DASH_SQUARES')[pattern])))
    raise ValueError(f'unknown line pattern {pattern!r}; known: {sorted(('solid', 'none') + tuple(_settings.constant('style', 'PATTERN_ORDER')))}')

def furniture_dash():
    return (0, tuple((v * _settings.constant('style', 'SQUARE_PT') for v in _settings.constant('style', 'HOUSE_DASH_SQUARES')['furniture'])))

def legend_dash_for(pattern, swatch_pt):
    spec = dash_for(pattern)
    if spec == 'solid' or pattern == 'none':
        return spec
    _, seq = spec
    period = sum(seq)
    if period <= 0:
        return spec
    cycles = max(1, int(-(-swatch_pt // period)))
    out = list(seq) * cycles
    out[-1] = 1000.0
    return (0, tuple(out))

def legend_swatch_pt(base_pt):
    return _settings.constant('style', 'LEGEND_SWATCH_SQUARES') * _settings.constant('style', 'SQUARE_PT')

def legend_handlelength(base_pt):
    return legend_swatch_pt(base_pt) / float(base_pt)

def pattern_for_index(index, n_series=None):
    if n_series == 1 or (n_series is not None and n_series > _settings.value('line_defaults')['grayscale_more_than']):
        return 'solid'
    return _settings.constant('style', 'PATTERN_ORDER')[index % len(_settings.constant('style', 'PATTERN_ORDER'))]

def apply(profile):
    matplotlib.rcdefaults()
    matplotlib.rcParams.update(_settings.rcparams())
    matplotlib.rcParams.update(profile.rcparams())
