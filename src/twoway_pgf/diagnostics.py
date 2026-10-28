"""Opt-in renderer diagnostics via the standard library logging interface."""
import logging

_LOGGER = logging.getLogger('twoway_pgf')

def trace(*values, sep=' ', end='\n', flush=False):
    message=sep.join(str(v) for v in values)
    if 'WARNING' in message: _LOGGER.warning(message.strip())
    else: _LOGGER.debug(message.rstrip())
