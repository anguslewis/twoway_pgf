"""CLI: render a specification or copy editable defaults."""
import argparse
from .bridge import run_spec

def main():
    parser=argparse.ArgumentParser(prog='twoway_pgf')
    sub=parser.add_subparsers(dest='command',required=True)
    render=sub.add_parser('render')
    render.add_argument('spec')
    render.add_argument('--settings')
    render.add_argument('--timeout',type=float,default=600)
    copy=sub.add_parser('copy-settings')
    copy.add_argument('destination')
    args=parser.parse_args()
    if args.command=='copy-settings':
        from .settings import copy_defaults
        print(copy_defaults(args.destination))
    else: run_spec(args.spec,settings=args.settings,timeout=args.timeout)

if __name__=='__main__': main()
