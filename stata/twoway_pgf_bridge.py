"""Stata boundary: early version preflight, then a shell-free render child."""
import importlib.metadata
import sys

expected = '0.1.1'
command = ('twoway_pgf_setup, install (using existing Conda), or '
           'twoway_pgf_setup, python("/path/to/prepared/environment/bin/python")')
if sys.version_info[:3] != (3, 12, 14):
    raise RuntimeError('twoway_pgf requires the pinned Python 3.12.14; selected '
                       f'{sys.version.split()[0]} at {sys.executable}. '
                       f'Use {command}; then restart Stata if Python is initialized.')
try:
    installed = importlib.metadata.version('twoway-pgf')
except importlib.metadata.PackageNotFoundError:
    installed = 'not installed'
if installed != expected:
    raise RuntimeError(f'twoway_pgf wrapper {expected}; backend {installed}. '
                       f'Install matching backend: {command}; then restart Stata.')
from twoway_pgf.installation import check_version
check_version(expected, command)
if sys.argv[1] != '--check':
    from twoway_pgf.bridge import run_spec
    try:
        run_spec(sys.argv[1], settings=sys.argv[2] or None,
                 timeout=float(sys.argv[3]), manifest_dir=sys.argv[4] or None,
                 texbin=sys.argv[5] or None)
    except BaseException as exc:
        raise RuntimeError('twoway_pgf render failed; see child traceback above') from exc
