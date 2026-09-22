"""Separate external validation; does not launch or change the parking UI."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from parking_probe.pklot_evaluation import run, console_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('all', 'prepare', 'fit', 'calibrate', 'test'), default='all')
    args = parser.parse_args()
    result = run(args.phase)
    console_summary(result)


if __name__ == '__main__':
    main()
