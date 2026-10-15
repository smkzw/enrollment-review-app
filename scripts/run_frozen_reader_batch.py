"""Run an explicitly selected page batch serially through the product reader."""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--pages', nargs='+', type=int, required=True)
    parser.add_argument('--lane', choices=['main-A', 'main-B'], required=True)
    parser.add_argument('--effort', choices=['low', 'high', 'max'], required=True)
    parser.add_argument('--provider')
    parser.add_argument('--model')
    parser.add_argument('--context-layout', choices=['baseline', 'stable-prefix', 'source-reading'], default='baseline')
    args = parser.parse_args()
    if len(set(args.pages)) != len(args.pages) or min(args.pages) < 0:
        parser.error('Page indices must be unique and nonnegative')
    for page in args.pages:
        command = [sys.executable, '-m', 'scripts.run_frozen_product_reader',
                   '--frozen', args.frozen, '--output', f'{args.output_root}/{args.label}-page-{page}',
                   '--lane', args.lane, '--effort', args.effort, '--page-index', str(page),
                   '--context-layout', args.context_layout]
        for flag in ['provider', 'model']:
            value = getattr(args, flag)
            if value:
                command.extend(['--' + flag, value])
        # A process error requires inspection; recorded reader failures remain evidence.
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
