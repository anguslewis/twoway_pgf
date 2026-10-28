from . import settings as _settings
def _hex(rgb):
    r, g, b = rgb
    for channel in (r, g, b):
        if not 0 <= channel <= 255:
            raise ValueError(f'channel out of range in {rgb!r}')
    return f'#{r:02X}{g:02X}{b:02X}'

def p(i):
    if i < 1: raise ValueError('palette index must be >= 1')
    palette = _settings.value('palette')
    return palette[(i - 1) % len(palette)]

def gs(n):
    if not 0 <= n <= 16:
        raise ValueError(f'gs index must be in 0..16, got {n}')
    level = min(16 * n, 255)
    return _hex((level, level, level))

def series_color(index):
    return p(index + 1)

def _l_star_to_y(l_star):
    l_star = max(0.0, min(100.0, float(l_star)))
    if l_star > 8.0:
        return ((l_star + 16.0) / 116.0) ** 3
    return l_star / 903.3

def _y_to_grey(y):
    y = max(0.0, min(1.0, float(y)))
    if y <= 0.0031308:
        channel = y * 12.92
    else:
        channel = 1.055 * y ** (1 / 2.4) - 0.055
    level = int(round(max(0.0, min(1.0, channel)) * 255))
    return _hex((level, level, level))

def _l_star_to_grey(l_star):
    return _y_to_grey(_l_star_to_y(l_star))

def grey_ramp(n, reserve_black=False):
    if n < 1:
        raise ValueError(f'need at least one shade, got {n}')
    y_dark, y_light = (_l_star_to_y(_settings.constant('colors', 'RAMP_DARK_L')), _l_star_to_y(_settings.constant('colors', 'RAMP_LIGHT_L')))
    if n == 1:
        return [_y_to_grey(y_dark if not reserve_black else y_light)]
    if reserve_black:
        step = (y_light - y_dark) / n
        levels = [y_dark + step * (i + 1) for i in range(n)]
    else:
        step = (y_light - y_dark) / (n - 1)
        levels = [y_dark + step * i for i in range(n)]
    return [_y_to_grey(v) for v in levels]

def line_color(index):
    if index < 0:
        raise ValueError(f'series index must be >= 0, got {index}')
    return p(index % min(len(_settings.value('palette')), _settings.value('line_defaults')['palette_limit'] or len(_settings.value('palette'))) + 1)

def intensity(color_hex, factor):
    if not 0 <= factor <= 1:
        raise ValueError(f"intensity factor must be in 0..1 (Stata intensity 0..100); got {factor}. Stata's >100 branch (which oversaturates rather than fades) is not implemented.")
    from matplotlib.colors import to_hex, to_rgba
    rgba = to_rgba(color_hex)
    if rgba[3] != 1: raise ValueError('fill intensity requires an opaque color')
    color_hex = to_hex(rgba).upper()
    rgb = tuple((int(round(255 - factor * (255 - int(color_hex[i:i + 2], 16)))) for i in (1, 3, 5)))
    return _hex(rgb)

def bar_fill(color_hex, depth=0):
    if depth < 0:
        raise ValueError(f'bar stack depth must be >= 0, got {depth}')
    out = intensity(color_hex, _settings.constant('colors', 'BAR_INTENSITY'))
    for _ in range(depth):
        out = intensity(out, _settings.constant('colors', 'BAR_STACK_FADE'))
    return out

def lighten(color_hex, amount=0.45):
    if not 0 <= amount <= 1:
        raise ValueError(f'amount must be in 0..1, got {amount}')
    return intensity(color_hex, 1.0 - amount)

def resolve(spec):
    if not isinstance(spec, str):
        return spec
    token = spec.strip()
    lowered = token.lower()
    if lowered.startswith('p') and lowered[1:].isdigit():
        return p(int(lowered[1:]))
    if lowered.startswith('gs') and lowered[2:].isdigit():
        return gs(int(lowered[2:]))
    parts = token.replace(',', ' ').split()
    if len(parts) == 3 and all((q.isdigit() for q in parts)):
        channels = [int(q) for q in parts]
        if all((0 <= c <= 255 for c in channels)):
            return _hex(tuple(channels))
        raise ValueError(f'RGB channels must be 0-255, got {token!r}')
    named = {'black': '#000000', 'white': '#FFFFFF', 'grid': _settings.constant('colors', 'GRID'), 'tick': _settings.constant('colors', 'TICK'), 'axisline': _settings.constant('colors', 'AXISLINE'), 'xyline': _settings.constant('colors', 'XYLINE'), 'refmarker': _settings.constant('colors', 'REFMARKER'), 'col_g': _settings.constant('colors', 'COL_G'), 'text': _settings.constant('colors', 'TEXT')}
    from matplotlib.colors import to_hex, to_rgba
    if lowered == 'none': return 'none'
    color = named.get(lowered, token)
    return to_hex(color, keep_alpha=to_rgba(color)[3] != 1).upper()
