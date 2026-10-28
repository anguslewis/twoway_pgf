"""Explicit setup diagnostics; ordinary rendering never calls installers."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


def check_version(expected, install_command=None):
    from . import __version__
    installed = importlib.metadata.version('twoway-pgf')
    if installed != expected or __version__ != expected:
        command = install_command or f'{sys.executable} -m pip install twoway-pgf=={expected}'
        raise RuntimeError(f'twoway_pgf wrapper {expected}; backend {installed} '
                           f'(loaded module {__version__}). Install the matching backend: {command}. '
                           'Restart Stata if Python is already initialized.')


def diagnose(expected, texbin=None):
    check_version(expected)
    versions = {name: importlib.metadata.version(name) for name in ('numpy', 'pandas', 'matplotlib')}
    wanted = {'numpy': '2.2.6', 'pandas': '2.3.3', 'matplotlib': '3.10.9'}
    if sys.version_info[:3] != (3, 12, 14) or versions != wanted:
        raise RuntimeError(f'Pinned environment required: Python 3.12.14, {wanted}; got '
                           f'Python {platform.python_version()}, {versions}')
    # Import compiled dependencies.
    import numpy
    import pandas
    import matplotlib
    env = os.environ.copy()
    if texbin:
        texbin = str(Path(texbin).expanduser().resolve(strict=True))
        if not Path(texbin).is_dir():
            raise ValueError('texbin must be a directory containing TeX executables')
        env['PATH'] = texbin + os.pathsep + env.get('PATH', '')
    engine = shutil.which('pdflatex', path=env.get('PATH'))
    kpse = shutil.which('kpsewhich', path=env.get('PATH'))
    instruction = ('If TeX is already installed, select its executable directory with texbin("/path/to/tex/bin"); '
                   'MacTeX normally uses texbin("/Library/TeX/texbin"). Finder/Dock-launched Stata may lack your terminal PATH. '
                   'Otherwise, Install TeX Live (MacTeX on macOS), including PGF and Computer Modern '
                   'T1 fonts, manually; then rerun setup with texbin("/path/to/tex/bin").')
    if not engine or not kpse:
        raise RuntimeError('TeX not found: pdflatex and kpsewhich are required. ' + instruction)
    packages = ['pgf.sty', 'fontenc.sty', 'lmodern.sty', 'cmr10.tfm', 'ec-lmr10.tfm']
    for package in packages:
        result = subprocess.run([kpse, package], env=env, capture_output=True, text=True, timeout=30)
        if result.returncode or not result.stdout.strip():
            raise RuntimeError(f'TeX prerequisite missing: {package}. ' + instruction)
    with tempfile.TemporaryDirectory(prefix='twoway-pgf-tex-') as directory:
        path = Path(directory)
        (path / 'diagnostic.tex').write_text(r'''\documentclass{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{pgf}
\pagestyle{empty}
\begin{document}
Serif $x^2$ {\sffamily Sans 0123}
\begin{pgfpicture}\pgfpathmoveto{\pgfpoint{0pt}{0pt}}
\pgfpathlineto{\pgfpoint{10pt}{10pt}}\pgfusepath{stroke}\end{pgfpicture}
\end{document}
''')
        result = subprocess.run([engine, '-interaction=nonstopmode', '-halt-on-error',
                                 '-no-shell-escape', 'diagnostic.tex'], cwd=path, env=env,
                                capture_output=True, text=True, timeout=90)
        if result.returncode or not (path / 'diagnostic.pdf').is_file():
            raise RuntimeError('TeX minimal compile failed. ' + instruction + '\n' + result.stdout[-5000:])
    version = subprocess.run([engine, '--version'], env=env, capture_output=True,
                             text=True, check=True, timeout=30).stdout.splitlines()[0]
    # Record the canonical bin directory and the executable's original name.
    executable = Path(sys.executable).absolute()
    return {'backend': expected, 'python_exec': str(executable.parent.resolve() / executable.name),
            'python': platform.python_version(), 'dependencies': versions,
            'platform': platform.platform(), 'machine': platform.machine(),
            'texbin': texbin or str(Path(engine).parent), 'tex_engine': engine,
            'tex_version': version, 'compile': 'PASS'}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected', required=True)
    parser.add_argument('--texbin')
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    result = diagnose(args.expected, args.texbin)
    # Write the diagnostic success receipt.
    receipt = Path(args.receipt)
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
