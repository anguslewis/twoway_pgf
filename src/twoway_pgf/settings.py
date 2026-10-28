"""Load one complete visual settings file for each call; resolve named formats.

Objects merge recursively; arrays replace. Helpers share context-local immutable
snapshots. The rendering API serializes in-process calls.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
from types import MappingProxyType
from collections.abc import Mapping

_STATE = ContextVar('twoway_pgf_settings', default=None)
DEFAULT_PATH = Path(__file__).with_name('visual_settings.json')
FORMAT_KEYS = {'extends','width_in','height_in','font_family','base_pt','tex_preamble','max_points','legend_max_cols','axis_title_ratio','tick_nbins','tick_min_n','ink_scale','grid_linewidth','unclip_boundary','layout','visual','metrics_font_family','metrics_tex_preamble'}
LAYOUT_KEYS = {'region_w_in','region_h_in','slot_w_in','pad_left_in','pad_right_in','pad_top_in','leading_in','legend_extra_in','centre_narrow_ink','square'}
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_-]*\Z')


def plain(obj):
    if isinstance(obj, Mapping): return {k: plain(v) for k,v in obj.items()}
    if isinstance(obj, (list,tuple)): return [plain(v) for v in obj]
    return obj


def freeze(obj):
    if isinstance(obj,dict): return MappingProxyType({k:freeze(v) for k,v in obj.items()})
    if isinstance(obj,list): return tuple(freeze(v) for v in obj)
    return obj


def merge(parent, child):
    out=deepcopy(parent)
    for key,val in child.items():
        out[key]=merge(out[key],val) if isinstance(val,dict) and isinstance(out.get(key),dict) else deepcopy(val)
    return out


def _pairs(pairs):
    out={}
    for key,val in pairs:
        if key in out: raise ValueError(f'duplicate key {key!r}')
        out[key]=val
    return out


def finite(obj, path='spec'):
    if isinstance(obj,Mapping):
        for key,val in obj.items(): finite(val,f'{path}.{key}')
    elif isinstance(obj,(tuple,list)):
        for i,val in enumerate(obj): finite(val,f'{path}[{i}]')
    elif isinstance(obj,(int,float)) and not math.isfinite(obj):
        raise ValueError(f'{path}: non-finite number {obj}')


def _positive(value,path,zero=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f'{path}: expected a finite {"nonnegative" if zero else "positive"} number')


def _keys(obj,keys,path):
    if not isinstance(obj,dict): raise ValueError(f'{path}: expected an object')
    if set(obj)-keys: raise ValueError(f'{path}: unknown keys {sorted(set(obj)-keys)}')


def _shape(obj,schema,path):
    """Validate settings against structural and type declarations."""
    if isinstance(schema,dict) and path.split('.')[-1] in {'STATA_LINEWIDTH_RELSIZE','STATA_TEXTSIZE_RELSIZE','STATA_SYMBOLSIZE_RELSIZE','HOUSE_DASH_SQUARES','STATA_SYMBOL_MARKER'}:
        if not isinstance(obj,dict) or not obj: raise ValueError(f'{path}: expected nonempty style map')
        for key,val in obj.items():
            if not isinstance(key,str) or not NAME.fullmatch(key): raise ValueError(f'{path}: invalid style name {key}')
            _shape(val,next(iter(schema.values())),f'{path}.{key}')
    elif isinstance(schema,dict):
        _keys(obj,set(schema),path)
        if set(schema)-set(obj): raise ValueError(f'{path}: missing keys {sorted(set(schema)-set(obj))}')
        for k,v in obj.items(): _shape(v,schema[k],f'{path}.{k}')
    elif schema=='number':
        if isinstance(obj,bool) or not isinstance(obj,(int,float)): raise ValueError(f'{path}: expected number')
    elif schema=='integer':
        if isinstance(obj,bool) or not isinstance(obj,int): raise ValueError(f'{path}: expected integer')
    elif schema=='boolean' and not isinstance(obj,bool): raise ValueError(f'{path}: expected boolean')
    elif schema=='string' and not isinstance(obj,str): raise ValueError(f'{path}: expected string')
    elif schema=='array' and not isinstance(obj,list): raise ValueError(f'{path}: expected array')
    elif schema=='nullable_integer' and obj is not None and (isinstance(obj,bool) or not isinstance(obj,int)): raise ValueError(f'{path}: expected integer or null')


def _validate_visual(v,path):
    from matplotlib.colors import is_color_like
    schema=json.loads(Path(__file__).with_name('settings_structure.json').read_text())
    _shape(v,schema,path)
    finite(v,path)
    if not v['palette']: raise ValueError(f'{path}.palette: must not be empty')
    for color in v['palette']:
        if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color): raise ValueError(f'{path}.palette: expected #RRGGBB, got {color!r}')
    d=v['line_defaults']
    for key in ['palette_limit','grayscale_more_than']:
        if d[key] is not None: _positive(d[key],f'{path}.line_defaults.{key}',zero=key=='grayscale_more_than')
    c=v['constants']
    for key in ['BACKGROUND','GRID','TICK','AXISLINE','XYLINE','REFMARKER','TEXT','COL_G','CI_AREA']:
        if not is_color_like(c['colors'][key]): raise ValueError(f'{path}.constants.colors.{key}: invalid color')
    for key in ['CI_AREA_ALPHA','BAR_INTENSITY','BAR_STACK_FADE']:
        if not 0 <= c['colors'][key] <= 1: raise ValueError(f'{path}.constants.colors.{key}: expected 0..1')
    if not 0 <= c['colors']['RAMP_DARK_L'] <= c['colors']['RAMP_LIGHT_L'] <= 100: raise ValueError(f'{path}: invalid grayscale endpoints')
    s=c['style']
    for key in ['STATA_LINEWIDTH_RELSIZE','STATA_TEXTSIZE_RELSIZE','STATA_SYMBOLSIZE_RELSIZE']:
        for k,val in s[key].items(): _positive(val,f'{path}.{key}.{k}',zero=key=='STATA_LINEWIDTH_RELSIZE')
    for name,seq in s['HOUSE_DASH_SQUARES'].items():
        if not seq or len(seq)%2: raise ValueError(f'{path}: dash {name} needs on/off pairs')
        for val in seq: _positive(val,f'{path}.dash.{name}')
    if not s['PATTERN_ORDER'] or any(p not in s['HOUSE_DASH_SQUARES'] for p in s['PATTERN_ORDER']): raise ValueError(f'{path}: invalid pattern order')
    if s['SYMBOLSIZE_DEFAULT'] not in s['STATA_SYMBOLSIZE_RELSIZE'] or s['SYMBOL_EDGE_WIDTH'] not in s['STATA_LINEWIDTH_RELSIZE']: raise ValueError(f'{path}: unknown symbol size/width')
    for key,val in v['strokes'].items():
        if isinstance(val,str) and val not in s['STATA_LINEWIDTH_RELSIZE']: raise ValueError(f'{path}.strokes.{key}: unknown width')
    for axis in [v['grid']['axis'],*v['grid']['chart_axis'].values()]:
        if axis not in ['both','x','y','none']: raise ValueError(f'{path}.grid: invalid axis {axis}')
    _semantic_visual(v,path)
    # Ask Matplotlib's own validators about all rc names and values.
    import matplotlib as mpl
    mpl.RcParams(rcparams(v))


def rcparams(visual=None):
    v=visual if visual is not None else value()
    rc=plain(v['rc'])
    from cycler import cycler
    c=v['constants']['colors']
    rc.update({'axes.prop_cycle':cycler(color=list(v['palette'])),
        'axes.grid':v['grid']['enabled'], 'axes.grid.axis':v['grid']['axis'] if v['grid']['axis']!='none' else 'both',
        'legend.handletextpad':v['legend']['initial_handletextpad'],
        'figure.facecolor':c['BACKGROUND'],'axes.facecolor':c['BACKGROUND'],'savefig.facecolor':c['BACKGROUND'],
        'text.color':c['TEXT'],'axes.labelcolor':c['TEXT'],'axes.edgecolor':c['AXISLINE'],
        'xtick.color':c['TICK'],'ytick.color':c['TICK'],'grid.color':c['GRID']})
    return rc


def load(path=None):
    # Read the registered settings path from the environment.
    path=Path(path or os.environ.get('TWOWAY_PGF_SETTINGS') or DEFAULT_PATH).expanduser().resolve()
    try:
        blob=path.read_bytes()
        config=json.loads(blob,object_pairs_hook=_pairs)
        finite(config,'settings')
        _keys(config,{'schema_version','default_formats','base','formats'},'settings')
        if type(config['schema_version']) is not int or config['schema_version'] != 1: raise ValueError('schema_version: expected 1')
        _validate_visual(config['base'],'base')
        if not isinstance(config['formats'],dict) or not config['formats']: raise ValueError('formats: expected nonempty object')
        resolved={}
        def resolve(name,trail=()):
            if name in trail: raise ValueError(f'formats.{name}: inheritance cycle {trail}')
            if name not in config['formats']: raise ValueError(f'formats.{name}: unknown parent/format; available {list(config["formats"])}')
            if not NAME.fullmatch(name): raise ValueError(f'formats.{name}: unsafe name')
            if name in resolved: return resolved[name]
            raw=config['formats'][name]
            _keys(raw,FORMAT_KEYS,f'formats.{name}')
            parent=resolve(raw['extends'],trail+(name,)) if 'extends' in raw else {}
            result=merge(parent,{k:v for k,v in raw.items() if k!='extends'})
            missing=FORMAT_KEYS-{'extends'}-set(result)
            if missing: raise ValueError(f'formats.{name}: missing {sorted(missing)}')
            for key in ['width_in','height_in','base_pt','axis_title_ratio','ink_scale','grid_linewidth','tick_nbins','tick_min_n']:
                _positive(result[key],f'formats.{name}.{key}')
            for key in ['tick_nbins','tick_min_n','legend_max_cols','max_points']:
                if result[key] is not None and (isinstance(result[key],bool) or not isinstance(result[key],int) or result[key]<1): raise ValueError(f'formats.{name}.{key}: positive integer or null required')
            if not isinstance(result['unclip_boundary'],bool): raise ValueError(f'formats.{name}.unclip_boundary: expected boolean')
            if result['font_family'] not in ['serif','sans-serif','monospace','cursive','fantasy']: raise ValueError(f'formats.{name}.font_family: invalid family')
            if not isinstance(result['tex_preamble'],str): raise ValueError(f'formats.{name}.tex_preamble: expected string')
            layout=result['layout']
            if layout is not None:
                _keys(layout,LAYOUT_KEYS,f'formats.{name}.layout')
                required=LAYOUT_KEYS-{'square'}
                if required-set(layout): raise ValueError(f'formats.{name}.layout: missing {sorted(required-set(layout))}')
                for boolean in ['square','centre_narrow_ink']:
                    if boolean in layout and not isinstance(layout[boolean],bool): raise ValueError(f'formats.{name}.layout.{boolean}: expected boolean')
                if layout.get('square'):
                    layout['region_w_in']=layout['region_h_in']
                for key in ['region_w_in','region_h_in','slot_w_in','leading_in']:
                    _positive(layout[key],f'formats.{name}.layout.{key}')
                for key in ['pad_left_in','pad_right_in','pad_top_in','legend_extra_in']:
                    if key!='legend_extra_in' or layout[key] is not None: _positive(layout[key],f'formats.{name}.layout.{key}',zero=True)
                if (result['font_family'],result['tex_preamble']) != (result['metrics_font_family'],result['metrics_tex_preamble']):
                    raise ValueError(f'formats.{name}: fixed layout font metrics must be calibrated for the chosen font/preamble; set layout to null for constrained layout')
                if layout['region_w_in'] > layout['slot_w_in'] or abs(layout['pad_left_in']+layout['slot_w_in']+layout['pad_right_in']-result['width_in'])>1e-5:
                    raise ValueError(f'formats.{name}.layout: region/padding does not fit canvas width')
            visual=merge(config['base'],result['visual'])
            _validate_visual(visual,f'formats.{name}.visual')
            resolved[name]=result
            return result
        for name in config['formats']: resolve(name)
        defaults=config['default_formats']
        if not isinstance(defaults,list) or not defaults or len(set(defaults))!=len(defaults): raise ValueError('default_formats: expected nonempty unique list')
        for name in defaults: resolve(name)
        return {'path':str(path),'sha256':sha256(blob).hexdigest(),'config':freeze(config),'formats':freeze(resolved),'selected':None,'visual':freeze(config['base'])}
    except (ValueError,KeyError,TypeError) as exc:
        raise ValueError(f'{path}: {exc}') from exc


@contextmanager
def context(path=None, overrides=None):
    token=_STATE.set({**load(path), 'overrides':freeze(deepcopy(overrides))})
    try: yield _STATE.get()
    finally: _STATE.reset(token)


def activate_format(name):
    state=_STATE.get()
    if state is None: raise RuntimeError('settings context is required')
    if name not in state['formats']: raise ValueError(f'{state["path"]}: unknown format {name!r}; available {list(state["formats"])}')
    _STATE.set({**state,'selected':name,'visual':freeze(merge(plain(state['config']['base']),plain(state['formats'][name]['visual'])))})


def value(key=None):
    state=_STATE.get()
    if state is None: raise RuntimeError('use render() or settings.context() before reading visual settings')
    return state['visual'] if key is None else state['visual'][key]


def constant(module,name): return value('constants')[module][name]


def provenance():
    s=_STATE.get()
    return {'path':s['path'],'sha256':s['sha256'],'format':s['selected'],'resolved_format':plain(s['formats'][s['selected']]),'resolved_visual':plain(s['visual']), 'requested_spec':plain(s.get('overrides'))}


def copy_defaults(destination):
    destination=Path(destination)
    with destination.open('xb') as file: file.write(DEFAULT_PATH.read_bytes())
    return destination


def _semantic_visual(v,path):
    from matplotlib.markers import MarkerStyle
    from matplotlib.colors import is_color_like
    c=v['constants'];s=c['style']
    for key in ['REFERENCE_SHORT_SIDE_PT','SQUARE_PT','LEGEND_SWATCH_SQUARES']:
        _positive(s[key],f'{path}.constants.style.{key}')
    for name,pair in s['STATA_SYMBOL_MARKER'].items():
        if len(pair)!=2 or not isinstance(pair[0],str) or not isinstance(pair[1],bool): raise ValueError(f'{path}.STATA_SYMBOL_MARKER.{name}: expected [marker, filled_boolean]')
        MarkerStyle(pair[0])
    if v['scatter']['symbol'] not in s['STATA_SYMBOL_MARKER']: raise ValueError(f'{path}.scatter.symbol: unknown symbol')
    seq=s['HOUSE_DASH_SQUARES']['furniture']
    if not seq or len(seq)%2: raise ValueError(f'{path}.FURNITURE_DASH_SQUARES: expected on/off pairs')
    for val in seq: _positive(val,f'{path}.FURNITURE_DASH_SQUARES')
    for module,entries in c.items():
        if module in ['style','colors']: continue
        for key,val in entries.items():
            if isinstance(val,(int,float)) and 'ZORDER' not in key:
                _positive(val,f'{path}.constants.{module}.{key}',zero=key in ['_LEGEND_PAD_IN','WHISKER_PAD_FRACTION'])
            if key.endswith('LIGHTEN') and not 0<=val<=1: raise ValueError(f'{path}.{key}: expected 0..1')
            if key.endswith('WIDTH') and isinstance(val,str) and val not in s['STATA_LINEWIDTH_RELSIZE']: raise ValueError(f'{path}.{key}: unknown width')
    for name in ['RASTER_AUTO_THRESHOLD']:
        val=c['primitives.scatter'][name]
        if type(val) is not int or val<1: raise ValueError(f'{path}.{name}: positive integer required')
    val=c['primitives.hexbin']['_RAMP_STEPS']
    if type(val) is not int or val<2: raise ValueError(f'{path}._RAMP_STEPS: integer >=2 required')
    if not 0<c['primitives.hexbin']['KEY_SPAN_FRAC']<=1: raise ValueError(f'{path}.KEY_SPAN_FRAC: expected (0,1]')
    if type(v['legend']['columns']) is not int or v['legend']['columns']<1: raise ValueError(f'{path}.legend.columns: positive integer required')
    for key in ['handletextpad','initial_handletextpad','separate_seed_height_in']: _positive(v['legend'][key],f'{path}.legend.{key}',zero=key in ['handletextpad','initial_handletextpad'])
    def color(token,key):
        if not isinstance(token,str): raise ValueError(f'{key}: expected color string')
        if re.fullmatch(r'p[1-9][0-9]*',token) or re.fullmatch(r'gs(?:[0-9]|1[0-6])',token): return
        if not is_color_like(token): raise ValueError(f'{key}: invalid color {token}')
    color(c['primitives.bar']['ERROR_MARKER_FACE_COLOR'],path+'.error_marker_face_color')
    color(c['primitives.waterfall']['CONNECTOR_COLOR'],path+'.connector_color')
    color(v['line_defaults']['emphasis_color'],path+'.line_defaults.emphasis_color')
    if v['line_defaults']['emphasis_pattern'] not in ['solid','none',*s['HOUSE_DASH_SQUARES']]: raise ValueError(f'{path}.emphasis_pattern: unknown pattern')
    defaults=v['spec_defaults']
    for table in ['_BAR_FIELDS','_WATERFALL_FIELDS']:
        width=defaults[table]['bar_width']
        if not 0<width<=1: raise ValueError(f'{path}.{table}.bar_width: expected (0,1]')
    if not 0<=defaults['_BAR_FIELDS']['group_gap']<1: raise ValueError(f'{path}.group_gap: expected [0,1)')
    for key in ['up_color','down_color','total_color']: color(defaults['_WATERFALL_FIELDS'][key],path+'.'+key)
    _positive(defaults['_SCATTER_FIELDS']['raster_dpi'],path+'.raster_dpi')
    h=defaults['_HEXBIN_FIELDS']
    if h['key_mode'] not in ['continuous','substeps','ticks']: raise ValueError(f'{path}.key_mode: invalid mode')
    for key in ['key_steps','key_substeps']:
        if type(h[key]) is not int or h[key] < (2 if key=='key_steps' else 1): raise ValueError(f'{path}.{key}: invalid count')
    _positive(h['legend_labelspacing'],path+'.legend_labelspacing',zero=True)
    if not isinstance(h['ramp'],list) or len(h['ramp'])!=2: raise ValueError(f'{path}.ramp: expected two color tokens')
    for token in h['ramp']: color(token,path+'.ramp')
    ref=defaults['_REFLINE_FIELDS'];color(ref['color'],path+'.reference.color')
    if ref['pattern'] not in ['solid','none',*s['HOUSE_DASH_SQUARES']]: raise ValueError(f'{path}.reference.pattern: unknown pattern')
    if isinstance(ref['linewidth'],str):
        if ref['linewidth'] not in s['STATA_LINEWIDTH_RELSIZE']: raise ValueError(f'{path}.reference.linewidth: unknown width')
    else: _positive(ref['linewidth'],path+'.reference.linewidth',zero=True)
