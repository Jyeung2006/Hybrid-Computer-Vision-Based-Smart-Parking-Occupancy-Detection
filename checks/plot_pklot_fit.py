"""Optional diagnostic plot from saved fitting scores; never reads test pixels."""
import json
from pathlib import Path
import sys

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from parking_probe.sources import read_image, write_image


def main():
    manifest = json.loads((ROOT/'data/pklot/partitions.json').read_text())
    geometries = set()
    for row in manifest['partitions']['fit']:
        key = json.dumps(row['slots'][0]['polygon'])
        if key in geometries:
            continue
        geometries.add(key)
        image = read_image(ROOT/'data/pklot'/row['image'])
        for slot in row['slots']:
            cv2.polylines(image,[np.int32(slot['polygon'])],True,(0,255,255),2)
        cv2.putText(image,row['frame_id'],(15,35),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,0,255),2)
        write_image(ROOT/f'runs/verification/pklot-fit-geometry-{len(geometries)-1}.png',image)
    rows = json.loads((ROOT/'data/pklot/experiment/fit-scores.json').read_text())
    fitted = json.loads((ROOT/'data/pklot/experiment/fit.json').read_text())['boundaries']
    fig, axes = plt.subplots(3, 2, figsize=(12, 9), layout='constrained')
    for i, bay in enumerate(('UFPR04-P01', 'UFPR04-P11', 'UFPR04-P28')):
        for j, method in enumerate(('reference', 'mog2')):
            ax = axes[i,j]
            bound = fitted[method][bay]
            for label, color in (('vacant','#087f8c'),('occupied','#c63e40')):
                scores = [r['score'] for r in rows if r['slot_id']==bay and r['method']==method and r['truth']==label]
                ax.hist(scores, bins=np.linspace(0,1,51), density=True, histtype='stepfilled',
                        alpha=.35, color=color, label=f'{label} (n={len(scores)})')
            ax.axvline(bound['vacant_max'], color='#087f8c', linestyle='--', label='vacant 95th percentile')
            ax.axvline(bound['occupied_min'], color='#c63e40', linestyle=':', label='occupied 5th percentile')
            ax.set(title=f'{bay} | {method} | {bound["status"]}', xlabel='Difference score' if method=='reference' else 'Foreground fraction', ylabel='Density', xlim=(0,1))
            ax.grid(alpha=.15)
            if i==0:
                ax.legend(fontsize=8)
    fig.suptitle('UFPR04 fitting data: more examples do not guarantee separable features\nOriginal production scores; no test observations used', fontsize=14)
    output = ROOT/'runs/verification/pklot-fit-score-distributions.png'
    fig.savefig(output, dpi=150)
    print(output)


if __name__=='__main__':
    main()
