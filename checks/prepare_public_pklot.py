"""Verify cached archive and prepare day-separated UFPR05/PUCPR manifests."""
import argparse
import json
from parking_probe.pklot_additional import prepare, VIEWS

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--view', choices=[*VIEWS, 'both'], default='both')
args = parser.parse_args()
selected = VIEWS if args.view == 'both' else (args.view,)
print(json.dumps(prepare(selected=selected), indent=2))
