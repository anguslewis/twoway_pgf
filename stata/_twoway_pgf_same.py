"""Compare the initialized host's interpreter with the selected interpreter."""
from pathlib import Path
import os
import sys

current = Path(sys.executable)
chosen = Path(sys.argv[1])
# Compare the canonical bin directories and executable identities.
if current.parent.resolve() != chosen.parent.resolve() or not os.path.samefile(current, chosen):
    raise RuntimeError(f'Python is already initialized at {sys.executable}; '
                       f'twoway_pgf requires {sys.argv[1]}. Restart Stata. '
                       'Previous registration is unchanged.')
