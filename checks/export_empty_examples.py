"""Export the actual verified-empty reference crops and provenance for review."""
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from parking_probe.sources import read_image
from parking_probe.vision import pixel_hash


def main():
    run=json.loads((ROOT/'runs/verification/empty-replay-check.json').read_text())
    out=ROOT/'assets/empty-review';out.mkdir(parents=True,exist_ok=True)
    manifest={'basis':'assistant_visual_review; demonstration_not_independent_accuracy',
              'analysis_directory':run['analysis_directory'],'sources':{}}
    for source,detail in run['sources'].items():
        cfg_path=Path(detail['config']);config=json.loads(cfg_path.read_text())
        entries=[];tiles=[]
        for slot in config['slots']:
            meta=slot.get('vehicle_empty_match')
            if not meta:continue
            paths=[slot['reference_image'],*slot.get('vehicle_empty_reference_images',[])]
            references=[]
            for number,name in enumerate(paths):
                image=read_image(cfg_path.parent/name)
                poly=np.array(slot['polygon'],np.int32);x,y,w,h=cv2.boundingRect(poly)
                mask=np.zeros(image.shape[:2],np.uint8);cv2.fillPoly(mask,[poly],255)
                # Neutral outside the polygon so adjacent cars are not labelled empty.
                crop=image[y:y+h,x:x+w].copy();crop[mask[y:y+h,x:x+w]==0]=230
                filename=f'{source}-{slot["id"]}-empty-{number}.png'
                assert cv2.imwrite(str(out/filename),crop)
                references.append({'source_frame':str(cfg_path.parent/name),'crop':filename,
                                   'full_frame_pixel_hash':pixel_hash(image)})
                if number==0:
                    tile=np.full((150,240,3),245,np.uint8)
                    scale=min(230/w,115/h);rw,rh=round(w*scale),round(h*scale)
                    tile[30:30+rh,5:5+rw]=cv2.resize(crop,(rw,rh))
                    cv2.putText(tile,slot['id'],(7,22),0,.6,(10,10,10),1,cv2.LINE_AA);tiles.append(tile)
            entries.append({'slot_id':slot['id'],'polygon':slot['polygon'],
                            'references':references,'empty_match_metadata':meta})
        if tiles:
            canvas=np.full((((len(tiles)+2)//3)*150,720,3),245,np.uint8)
            for i,tile in enumerate(tiles):canvas[(i//3)*150:(i//3+1)*150,(i%3)*240:(i%3+1)*240]=tile
            assert cv2.imwrite(str(out/f'{source}-empty-gallery.jpg'),canvas)
        manifest['sources'][source]={'config':str(cfg_path),'bay_count':len(entries),'bays':entries}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print({k:v['bay_count'] for k,v in manifest['sources'].items()})


if __name__=='__main__':main()
