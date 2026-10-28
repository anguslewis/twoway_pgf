"""Commit an already diagnosed interpreter after Stata accepts its selection."""
import os
from pathlib import Path
import sys
import tempfile

record = Path(sys.argv[1]).read_text()
values = record.splitlines()
if len(values) != 3 or values[0] != '0.1.0' or not Path(values[1]).is_file():
    raise RuntimeError('Invalid setup receipt; previous registration is unchanged')
registry = Path(sys.argv[2])
registry.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile(mode='w', dir=registry.parent, delete=False) as stream:
    stream.write(record)
    stage = stream.name
os.replace(stage, registry)
