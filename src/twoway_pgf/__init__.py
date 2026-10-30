"""LaTeX-native figures from Python or Stata."""
__version__ = '0.1.1'

def render(spec, manifest_dir=None, *, settings=None):
    from .api import render as render_impl
    return render_impl(spec, manifest_dir, settings=settings)

def render_spec_file(path, *, settings=None, manifest_dir=None):
    from .api import render_spec_file as render_impl
    return render_impl(path, settings=settings, manifest_dir=manifest_dir)
