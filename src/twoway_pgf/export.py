from .diagnostics import trace as _log
from . import settings as _settings
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path
import matplotlib
from matplotlib.transforms import Bbox
from .primitives import common as primitives_common
PGF_PROLOGUE = '%% twoway_pgf: scoped superscript/breqn compatibility and raster path.\n\\begingroup%\n\\providecommand{\\mathdefault}[1]{#1}%\n\\begingroup%\n\\catcode`\\^=7 %\n\\global\\let\\twpgfsuperscript=^%\n\\endgroup%\n\\let\\sp=\\twpgfsuperscript%\n\\providecommand{\\twpgfimagedir}{}%\n'
PGF_EPILOGUE = "%% twoway_pgf epilogue: closes the prologue's scope.\n\\endgroup%\n"
_TEX_HAZARDS = {'&': 'misplaced alignment tab', '#': 'macro parameter character', '~': 'renders as a non-breaking space, not a tilde'}
_FIGURE_RECT = re.compile('\\\\pgfpathrectangle\\{\\\\pgfpointorigin\\}\\{\\\\pgfqpoint\\{([\\d.]+)in\\}\\{([\\d.]+)in\\}\\}')

def _tex_version():
    result = subprocess.run([matplotlib.rcParams['pgf.texsystem'], '--version'], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()[0].strip()
CLIP_TOLERANCE_PT = 0.05

def _tight_with_axis_labels(fig, renderer):
    boxes = [fig.get_tightbbox(renderer)]
    inverse = fig.dpi_scale_trans.inverted()
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            if not axis.get_visible():
                continue
            found = axis.get_tightbbox(renderer)
            if found is not None and found.width and found.height:
                boxes.append(found.transformed(inverse))
    return Bbox.union(boxes)

def _assert_nothing_clipped(fig, pgf_path, profile):
    renderer = fig.canvas.get_renderer()
    box = fig.bbox_inches
    tight = _tight_with_axis_labels(fig, renderer)
    over = {'left': (box.x0 - tight.x0) * 72.0, 'right': (tight.x1 - box.x1) * 72.0, 'bottom': (box.y0 - tight.y0) * 72.0, 'top': (tight.y1 - box.y1) * 72.0}
    worst_side, worst = max(over.items(), key=lambda pair: pair[1])
    if worst <= CLIP_TOLERANCE_PT:
        _log(f'    [fit   ] nothing clipped; tightest side is {worst_side} with {-worst:.2f}pt of slack')
        return
    culprits = []
    for artist in fig.findobj():
        if not hasattr(artist, 'get_window_extent'):
            continue
        getter = getattr(artist, 'get_text', None)
        label = getter() if callable(getter) else None
        if not label:
            continue
        artist_box = artist.get_window_extent(renderer=renderer).transformed(fig.dpi_scale_trans.inverted())
        if not tight.containsx(artist_box.x0) or not tight.containsy(artist_box.y0):
            continue
        excess = max(box.x0 - artist_box.x0, artist_box.x1 - box.x1, box.y0 - artist_box.y0, artist_box.y1 - box.y1) * 72.0
        if excess > CLIP_TOLERANCE_PT:
            culprits.append((label, excess))
    culprits.sort(key=lambda pair: -pair[1])
    listed = '\n      '.join((f'{excess:6.2f}pt outside: {label!r}' for label, excess in culprits[:6]))
    raise RuntimeError(f"{pgf_path.name}: {worst:.2f}pt of content sits OUTSIDE the {profile.width_in:.3f}x{profile.height_in:.3f}in figure box, on the {worst_side}. A .pgf clips to its own rectangle, so this text will be CUT OFF in the document -- silently, and the preview PDF will not show it either.\n    per side (points outside): left {over['left']:.2f}, right {over['right']:.2f}, bottom {over['bottom']:.2f}, top {over['top']:.2f}\n    responsible:\n      {listed or '(no text artist identified)'}\n    Fixes, in order of preference: shorten the label; reduce the legend's cols() so it wraps instead of running off the edges; on a narrow profile lower its axis_title_ratio; or use a wider profile. Symmetric left/right overflow means the content is simply WIDER THAN THE FIGURE, and no margin change will fix it.")

def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _save(fig, outdir, name, profile, data_path, spec, manifest_dir, preview=True):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f'{name}_{profile.name}'
    pgf_path = outdir / f'{stem}.pgf'
    preview_path = outdir / f'{stem}_preview.pdf'
    _log(f'    [export] {profile.name}: {profile.width_in:.4f} x {profile.height_in:.4f} in')
    if profile.unclip_boundary:
        for axes in fig.axes:
            primitives_common.unclip_gridlines(axes)
    rasterized = bool(getattr(fig, '_twpgf_rasterized', False))
    raster_dpi = getattr(fig, '_twpgf_raster_dpi', None)
    for stale in sorted(outdir.glob(f'{stem}-img*.png')):
        stale.unlink()
    if rasterized:
        fig.savefig(pgf_path, dpi=raster_dpi)
    else:
        fig.savefig(pgf_path)
    try:
        body = pgf_path.read_text()
        siblings = sorted(outdir.glob(f'{stem}-img*.png'))
        raster_macros = [m for m in ('\\includegraphics', '\\pgfimage') if m in body]
        if rasterized:
            if not siblings:
                raise RuntimeError(f'{pgf_path.name}: the spec asked for a rasterised layer but no side-car {stem}-img*.png was written. Either nothing was actually marked rasterized, or the backend changed how it emits rasters -- do not ship this figure, because a figure that silently fell back to vector at raster dpi is not what was asked for.')
            if not raster_macros:
                raise RuntimeError(f'{pgf_path.name}: a side-car {siblings[0].name} exists but the .pgf contains no \\includegraphics or \\pgfimage referencing it. The figure would ship with the raster missing.')
            for image in siblings:
                bare = '{' + image.name + '}'
                hooked = '{\\twpgfimagedir ' + image.name + '}'
                if bare not in body:
                    raise RuntimeError(f"{pgf_path.name}: expected a bare reference {bare} to rewrite, and it is not there. The PGF backend's image reference format has changed; the rewrite is no longer valid and the figure must not ship unchecked.")
                body = body.replace(bare, hooked)
            _log(f'    [raster] {len(siblings)} side-car image(s) at {raster_dpi} dpi: {[s.name for s in siblings]}')
            _log('    [raster] reference routed through \\twpgfimagedir -- a document that inputs this .pgf from a subdirectory must set that macro to the same prefix (see the README)')
        elif siblings or raster_macros:
            raise RuntimeError(f"{pgf_path.name} is NOT fully vector, and the spec did not ask for it: macros {raster_macros}, side-car images {[p.name for p in siblings]}. An unintended rasterised artist makes the .pgf reference a bare image filename, which breaks when the figure sits in a subdirectory of the document. Remove the set_rasterized(True) / set_rasterization_zorder / imshow, or ask for rasterisation explicitly (scatter's rasterize option).")
        pgf_path.write_text(PGF_PROLOGUE + body + PGF_EPILOGUE)
        _assert_nothing_clipped(fig, pgf_path, profile)
        match = _FIGURE_RECT.search(body)
        if match is None:
            raise RuntimeError(f'could not find the figure rectangle in {pgf_path.name}; the PGF output format has changed and the dimension check is no longer valid.')
        written_w, written_h = (float(match.group(1)), float(match.group(2)))
        for label, written, expected in (('width', written_w, profile.width_in), ('height', written_h, profile.height_in)):
            if abs(written - expected) > 0.0001:
                raise RuntimeError(f"{pgf_path.name} declares a {label} of {written}in but profile {profile.name} asks for {expected}in. The figure would not be at its final size in the document. A savefig(bbox_inches='tight') is the usual cause.")
        _log(f'    [check ] figure rect {written_w}in x {written_h}in matches the profile')
        hazards = []
        for text in re.findall('\\\\selectfont(.*?)\\}\\}%', body):
            for char, why in _TEX_HAZARDS.items():
                if any(len(text[:index]) - len(text[:index].rstrip('\\')) == 0 or (len(text[:index]) - len(text[:index].rstrip('\\'))) % 2 == 0 for index, value in enumerate(text) if value == char):
                    hazards.append((char, why, text[:60]))
        if hazards:
            raise RuntimeError(f'{pgf_path.name} contains raw TeX-hazard characters that matplotlib does not escape: {hazards}. Escape them in the spec (see twoway_pgf.texesc.escape) before they reach the figure.')
    except Exception:
        for doomed in [pgf_path, preview_path, *sorted(outdir.glob(f'{stem}-img*.png'))]:
            if doomed.exists():
                doomed.unlink()
                _log(f'    [refused] removed {doomed.name} -- a refused figure must not be left where \\input can find it')
        raise
    if preview:
        fig.savefig(preview_path)
        _log(f'    [export] preview {preview_path.name}')
    manifest_dir = Path(manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {'figure': stem, 'pgf': str(pgf_path), 'pgf_sha256': _sha256(pgf_path), 'pgf_bytes': pgf_path.stat().st_size, 'profile': {'name': profile.name, 'width_in': profile.width_in, 'height_in': profile.height_in, 'font_family': profile.font_family, 'base_pt': profile.base_pt, 'document': profile.document}, 'input_data': str(data_path), 'input_data_sha256': _sha256(data_path), 'spec': spec, 'settings': _settings.provenance(), 'versions': {'python': sys.version.split()[0], 'matplotlib': matplotlib.__version__, 'texsystem': matplotlib.rcParams['pgf.texsystem'], 'tex': _tex_version(), 'platform': platform.platform()}}
    manifest_path = manifest_dir / f'{stem}.manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str))
    _log(f'    [export] manifest {manifest_path}')
    return {'pgf': pgf_path, 'preview': preview_path if preview else None, 'manifest': manifest_path, 'bytes': manifest['pgf_bytes']}


def save(fig, outdir, name, profile, data_path, spec, manifest_dir, preview=True):
    """Validate the bundle, archive existing outputs, and publish staged files.

    The manifest is published last. Concurrent rendering to the same stem is
    unsupported.
    """
    import os
    import tempfile
    import uuid
    import shutil
    outdir, manifest_dir = Path(outdir), Path(manifest_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    stem = f'{name}_{profile.name}'
    with tempfile.TemporaryDirectory(prefix='.twoway-pgf-', dir=outdir) as directory, tempfile.TemporaryDirectory(prefix='.twoway-pgf-', dir=manifest_dir) as manifest_stage:
        stage = Path(directory)
        written = _save(fig, stage, name, profile, data_path, spec, stage / 'manifests', preview)
        manifest = json.loads(written['manifest'].read_text())
        manifest['pgf'] = str(outdir / written['pgf'].name)
        manifest['versions']['twoway_pgf'] = __import__('twoway_pgf').__version__
        import numpy, pandas
        manifest['versions'].update(numpy=numpy.__version__, pandas=pandas.__version__)
        manifest['raster_sidecars'] = {f.name: _sha256(f) for f in stage.glob(stem+'-img*.png')}
        staged_manifest = Path(manifest_stage) / written['manifest'].name
        staged_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        previous = [outdir / f'{stem}.pgf', outdir / f'{stem}_preview.pdf', *outdir.glob(stem+'-img*.png')]
        manifest_path = manifest_dir / written['manifest'].name
        # Archive the success manifest before replacing output files.
        previous.insert(0, manifest_path)
        existing = [path for path in previous if path.exists()]
        if existing:
            archive = outdir / '.archive' / (stem+'-'+uuid.uuid4().hex)
            archive.mkdir(parents=True)
            for path in existing: shutil.move(str(path), str(archive / path.name))
        for path in stage.iterdir():
            if path.is_file(): os.replace(path, outdir / path.name)
        os.replace(staged_manifest, manifest_path)
        return {'pgf':outdir / f'{stem}.pgf', 'preview':outdir / f'{stem}_preview.pdf' if preview else None,
                'manifest':manifest_path, 'bytes':written['bytes']}
