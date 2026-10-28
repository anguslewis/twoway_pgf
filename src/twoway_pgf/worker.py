"""Installed child entry point. A receipt is written only after all exports pass."""
import argparse
import json
from pathlib import Path
import traceback
from . import render_spec_file

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('spec')
    parser.add_argument('--settings')
    parser.add_argument('--manifest-dir')
    parser.add_argument('--receipt')
    parser.add_argument('--nonce')
    args=parser.parse_args()
    try:
        result=render_spec_file(args.spec,settings=args.settings,manifest_dir=args.manifest_dir)
        if args.receipt:
            Path(args.receipt).write_text(json.dumps({'nonce':args.nonce,'outputs':result},default=str))
    except BaseException as exc:
        # Report child exceptions and raise a render failure.
        traceback.print_exc()
        raise RuntimeError('render failed before completion') from exc

if __name__=='__main__': main()
