"""Standard-library-only child-process boundary, including for embedded Stata."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import uuid

class RenderFailed(RuntimeError):
    """A render child failed."""


def run_spec(path, *, settings=None, python=None, timeout=600, manifest_dir=None, texbin=None):
    if isinstance(timeout,bool) or not math.isfinite(timeout) or timeout<=0:
        raise ValueError('timeout must be a finite positive number of seconds')
    path=Path(path).resolve()
    with tempfile.TemporaryDirectory(prefix='twoway-pgf-') as directory:
        receipt=Path(directory)/'receipt.json'
        nonce=uuid.uuid4().hex
        args=[str(python or sys.executable),'-m','twoway_pgf.worker',str(path),'--receipt',str(receipt),'--nonce',nonce]
        if settings: args+=['--settings',str(Path(settings).resolve())]
        if manifest_dir: args+=['--manifest-dir',str(Path(manifest_dir).resolve())]
        env=os.environ.copy()
        # Clear PYTHONPATH and disable user-site imports in the child.
        env.pop('PYTHONPATH',None)
        env['PYTHONNOUSERSITE']='1'
        if texbin:
            env['PATH']=str(Path(texbin).resolve())+os.pathsep+env.get('PATH','')
        library = Path(python or sys.executable).resolve().parent.parent / 'lib'
        if sys.platform.startswith('linux') and library.is_dir():
            env['LD_LIBRARY_PATH'] = str(library) + (os.pathsep + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
        for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']: env[key]='1'
        env['MPLCONFIGDIR']=str(Path(directory)/'mpl')
        env['XDG_CACHE_HOME']=str(Path(directory)/'cache')
        Path(env['XDG_CACHE_HOME']).mkdir()
        process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,start_new_session=os.name=='posix')
        try:
            output,_=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            if os.name=='posix': os.killpg(process.pid,signal.SIGKILL)
            else: process.kill()
            output,_=process.communicate()
            print(output,end='',flush=True)
            raise RenderFailed(f'render timed out after {timeout:g}s') from exc
        print(output,end='',flush=True)
        if process.returncode!=0: raise RenderFailed(f'render child exited with status {process.returncode}')
        if not receipt.is_file(): raise RenderFailed('render child exited without a success receipt (possible SystemExit)')
        result=json.loads(receipt.read_text())
        if result.get('nonce')!=nonce: raise RenderFailed('render receipt does not match this invocation')
        return result['outputs']
