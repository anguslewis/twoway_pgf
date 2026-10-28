from .diagnostics import trace as _log
from . import settings as _settings
import json
from pathlib import Path
import pandas as pd
from . import export, formats, layout, spec as spec_module, style
from .primitives import bar as bar_primitive
from .primitives import hexbin as hexbin_primitive
from .primitives import line as line_primitive
from .primitives import scatter as scatter_primitive
from .primitives import waterfall as waterfall_primitive
_PRIMITIVES = {'line': line_primitive.build, 'waterfall': waterfall_primitive.build, 'bar': bar_primitive.build, 'scatter': scatter_primitive.build, 'hexbin': hexbin_primitive.build}

def _load_data(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'plot data not found: {path}\nThe producing code must write the plot-data CSV before the figure is built.')
    frame = pd.read_csv(path)
    _log(f'    [data  ] {path}')
    _log(f'    [data  ] {len(frame)} rows x {len(frame.columns)} cols: {list(frame.columns)}')
    if frame.empty:
        raise ValueError(f'plot data {path} has no rows.')
    return frame

def _render_separate_legend(payload, outdir, name, profile, data_path, spec, manifest_dir):
    import copy
    handles, labels, ncols, fontsize = payload
    figure = _figure(figsize=(profile.width_in, _settings.value('legend')['separate_seed_height_in']))
    legend = figure.legend(handles, labels, loc='center', ncols=ncols, frameon=False, fontsize=fontsize, borderpad=0.0, borderaxespad=0.0, handletextpad=_settings.value('legend')['handletextpad'])
    figure.canvas.draw()
    box = legend.get_window_extent(figure.canvas.get_renderer()).transformed(figure.dpi_scale_trans.inverted())
    width = box.width + 2 * _settings.constant('api', '_LEGEND_PAD_IN')
    height = box.height + 2 * _settings.constant('api', '_LEGEND_PAD_IN')
    figure.set_size_inches(width, height)
    legend.set_bbox_to_anchor((0.5, 0.5), transform=figure.transFigure)
    figure.canvas.draw()
    leg_profile = copy.copy(profile)
    leg_profile.name = f'{profile.name}_leg'
    leg_profile.width_in = width
    leg_profile.height_in = height
    leg_profile.layout = None
    _log(f'    [legend ] separate: {len(labels)} entries in {ncols} column(s), {width:.4f} x {height:.4f}in')
    written = export.save(figure, outdir, name, leg_profile, data_path, spec, manifest_dir, preview=spec['preview'])
    figure.clear()
    return (leg_profile.name, written)

def _render(raw_spec, manifest_dir=None):
    if not isinstance(raw_spec, dict): raise ValueError('a spec must be a dictionary')
    targets = formats.resolve(raw_spec.get('formats'))
    _settings.activate_format(targets[0].name)
    figure_spec = spec_module.normalize(raw_spec)
    legend = figure_spec.get('legend') or {}
    if legend.get('show', True) and legend.get('position') == 'separate':
        if any(profile.layout is None for profile in targets):
            raise ValueError('separate legends require fixed layout; choose a fixed-layout '
                             'format such as paper, or use a bottom legend with constrained layout')
    stems = [p.name for p in targets]
    if (figure_spec.get('legend') or {}).get('position') == 'separate':
        stems += [p.name + '_leg' for p in targets]
    if len(stems) != len(set(stems)):
        raise ValueError('selected formats collide with separate-legend output names')
    name = figure_spec['name']
    outdir = Path(figure_spec['outdir'])
    data_path = Path(figure_spec['data'])
    _log('=' * 74)
    _log(f"twoway_pgf: {figure_spec['type']} figure {name!r}")
    _log(f'    [out   ] {outdir}')
    _log(f"    [prof  ] {', '.join((p.name for p in targets))}")
    _log('=' * 74)
    frame = _load_data(data_path)
    if manifest_dir is None:
        manifest_dir = data_path.parent / 'manifests'
    results = {}
    for profile in targets:
        _log(f'\n--- profile {profile.name} {profile!r}')
        _settings.activate_format(profile.name)
        style.apply(profile)
        figure_spec = spec_module.normalize(raw_spec)
        figure = _figure()
        axes = figure.subplots()
        _PRIMITIVES[figure_spec['type']](figure, axes, frame, figure_spec, profile)
        laid_out = layout.apply(figure, axes, figure_spec, profile)
        export_profile = laid_out if laid_out is not None else profile
        results[profile.name] = export.save(figure, outdir, name, export_profile, data_path, figure_spec, manifest_dir, preview=figure_spec['preview'])
        payload = getattr(figure, '_twpgf_separate_legend', None)
        if payload is not None:
            leg_name, leg_written = _render_separate_legend(payload, outdir, name, export_profile, data_path, figure_spec, manifest_dir)
            results[leg_name] = leg_written
        figure.clear()
        _log(f"    [done  ] {results[profile.name]['pgf']}  ({results[profile.name]['bytes']:,} bytes)")
    _log('\n' + '=' * 74)
    for profile_name, written in results.items():
        _log(f"  {profile_name:8s} {written['pgf']}")
    _log('=' * 74)
    return results



def _figure(**kwargs):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_pgf import FigureCanvasPgf
    fig = Figure(**kwargs)
    FigureCanvasPgf(fig)
    return fig


from threading import RLock
_RENDER_LOCK = RLock()

def render(raw_spec, manifest_dir=None, *, settings=None):
    """Render a CSV-backed specification with a fresh settings snapshot."""
    import matplotlib as mpl
    _settings.finite(raw_spec)
    with _RENDER_LOCK, _settings.context(settings, overrides=raw_spec), mpl.rc_context():
        return _render(raw_spec, manifest_dir)


def render_spec_file(path, *, settings=None, manifest_dir=None):
    """Read either a bare spec or a {"spec": ...} envelope."""
    envelope = json.loads(Path(path).read_text(), object_pairs_hook=_settings._pairs)
    raw = envelope.get('spec', envelope)
    return render(raw, settings=settings, manifest_dir=manifest_dir)
