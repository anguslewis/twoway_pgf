"""Convert validated setup diagnostics to an atomic, plain-text registration."""
import json
import os
from pathlib import Path
import sys
import tempfile


def atomic_text(path, text):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        stream.write(text)
        stage = stream.name
    os.replace(stage, path)


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    values = [data['backend'], data['python_exec'], data['texbin']]
    if data.get('compile') != 'PASS' or any('\n' in v or '\r' in v for v in values):
        raise ValueError('Invalid setup diagnostic')
    atomic_text(sys.argv[2], '\n'.join(values) + '\n')


if __name__ == '__main__':
    main()
