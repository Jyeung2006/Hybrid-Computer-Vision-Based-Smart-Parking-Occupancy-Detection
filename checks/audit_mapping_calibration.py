"""Read-only audit of original bays, current mapping/calibration, and YOLO evidence."""
from collections import Counter
from itertools import combinations
import ast
import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import onnx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from parking_probe.areas import VIEWS
from parking_probe.comparison import consensus
from parking_probe.config import Config, validate_polygon
from parking_probe.monitor import recording_for_recipe
from parking_probe.vision import Analyzer
from parking_probe.yolo import YOLODetector, associate
from diagnose_unresolved import bay_candidates


def observations(directory):
    paths = [directory/'history.jsonl'] if (directory/'history.jsonl').exists() else sorted(directory.glob('*/history.jsonl'))
    return [item for path in paths for line in path.read_text().splitlines()
            for item in json.loads(line)['recordings']]


def indexed(items):
    return {(item['recording_id'], item['reference']['frame_id'], row['slot_id']): row
            for item in items for row in item['rows']}


def compare(old, current):
    common = old.keys() & current.keys()
    states = ('reference_state','mog2_state')
    return dict(matched_observations=len(common), classic_state_changes=sum(
        any(old[key][s] != current[key][s] for s in states) for key in common),
        original_consensus_to_current_final=dict(Counter(
            consensus(old[key]['reference_state'], old[key]['mog2_state'])+' -> '+current[key]['final_state']
            for key in common)),
        actual_final_transitions=dict(Counter(
            old[key].get('final_state',consensus(old[key]['reference_state'],old[key]['mog2_state']))+
            ' -> '+current[key]['final_state'] for key in common)))


def image_map(image, slots, coverage, detections=None):
    canvas = image.copy()
    if detections is not None:
        for d in detections:
            x1,y1,x2,y2 = map(round,d['box'])
            cv2.rectangle(canvas,(x1,y1),(x2,y2),(220,220,220),1)
    for slot in slots:
        color = {'calibrated':(60,200,40),'empty_only':(0,180,255),'no_reference':(180,50,240)}[coverage[slot['id']]]
        poly = np.int32(slot['polygon'])
        cv2.polylines(canvas,[poly],True,color,2)
        x,y = poly.mean(axis=0).astype(int)
        cv2.putText(canvas,slot['id'],(x-17,y+4),cv2.FONT_HERSHEY_SIMPLEX,.42,(0,0,0),3,cv2.LINE_AA)
        cv2.putText(canvas,slot['id'],(x-17,y+4),cv2.FONT_HERSHEY_SIMPLEX,.42,color,1,cv2.LINE_AA)
    canvas = cv2.copyMakeBorder(canvas,0,40,0,0,cv2.BORDER_CONSTANT,value=(20,20,20))
    cv2.putText(canvas,'Green: both calibrated | Amber: empty reference only | Purple: no empty reference',
        (12,canvas.shape[0]-15),cv2.FONT_HERSHEY_SIMPLEX,.49,(240,240,240),1,cv2.LINE_AA)
    return canvas


def main():
    run = Path(json.loads((ROOT/'runs/verification/decision-check.json').read_text())['analysis_directory'])
    out = ROOT/'runs/verification/mapping-calibration-audit';out.mkdir(parents=True,exist_ok=True)
    items = observations(run);current=indexed(items)
    original = indexed(observations(ROOT/'runs/comparison/20260917T161258_089149Z'))
    ssd = indexed(observations(ROOT/'runs/areas/20260918T185845_684414Z'))
    ssd_chad = {k:v for k,v in ssd.items() if k[0].startswith('chad')}
    original_recipe=json.loads((ROOT/'presets/chad-camera-1.json').read_text())
    expanded_recipe=json.loads((ROOT/'presets/chad-camera-1-expanded.json').read_text())
    preserved=all(all(expanded_recipe['slots'][i].get(k)==v for k,v in s.items())
        for i,s in enumerate(original_recipe['slots']))
    assert preserved
    report=dict(run=str(run),production_changed=False,original_recipe_entries_preserved=preserved,
        original_three_bays=compare(original,current),ssd_chad_to_current=compare(ssd_chad,current),
        sources={},models={},independent_accuracy_measured=False)
    manifest=json.loads((ROOT/'assets/models/yolov8s-manifest.json').read_text())
    for key,profile in manifest['profiles'].items():
        path=ROOT/'assets/models'/profile['file']
        model=onnx.load(path,load_external_data=False)
        meta={x.key:x.value for x in model.metadata_props}
        names=ast.literal_eval(meta['names'])
        assert len(names)==profile['class_count']
        assert all(names[int(k)]==v for k,v in profile['vehicle_classes'].items())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==profile['sha256']
        report['models'][key]=dict(architecture=manifest['architecture'],file=profile['file'],
            input_size=manifest['input_size'],output_classes=names,vehicle_class_mapping_correct=True,
            integrity_verified=True,source=profile['source'])
    detector=YOLODetector(); flat=[]
    for site_path in sorted(run.glob('*/site.json')):
        source=site_path.parent.name
        cfg=Config(Path(json.loads(site_path.read_text())['reference_config']))
        analyzer=Analyzer(cfg)
        mog=json.loads((site_path.parent/'mog2-calibration.json').read_text())
        recipe_file=('overhead-all-bays.json' if source=='overhead' else
            'chad-camera-1-expanded.json' if source=='chad' else source+'.json')
        recipe=json.loads((ROOT/'presets'/recipe_file).read_text())
        assert len({s['id'] for s in recipe['slots']})==len(recipe['slots'])
        assert len({s['bay_id'] for s in recipe['slots']})==len(recipe['slots'])
        width,height=recipe['analysis_resolution']
        assert (width,height)==(analyzer.width,analyzer.height)
        overlaps=[]
        for a,b in combinations(recipe['slots'],2):
            pa=np.float32(a['polygon']);pb=np.float32(b['polygon'])
            intersection,_=cv2.intersectConvexConvex(pa,pb)
            fraction=intersection/min(cv2.contourArea(pa),cv2.contourArea(pb))
            if fraction > .01: overlaps.append(dict(a=a['id'],b=b['id'],smaller_polygon_overlap=float(fraction)))
        selected=observations(site_path.parent)
        clip_id='chad-1' if source=='chad' else 'overhead-1' if source=='overhead' else source
        last=[x for x in selected if x['recording_id']==clip_id][-1]
        profile='aerial' if source=='overhead' else 'coco'
        recording=recording_for_recipe(VIEWS[clip_id].path,recipe)
        try:
            start_image=recording.read(0)
            last_image=recording.read(last['reference']['video_frame_index'])
        finally:recording.close()
        repeated=[detector.detect(last_image,profile) for _ in range(3)]
        assert repeated[0]==repeated[1]==repeated[2]
        fresh=associate(recipe['slots'],repeated[0],set(last['yolo']['requested_slot_ids']),.5 if profile=='aerial' else .82)
        saved={s['slot_id']:s['state'] for s in last['yolo']['slots']}
        assert all(saved[s['slot_id']]==s['state'] for s in fresh)
        raw=bay_candidates(recipe['slots'],repeated[0],.5 if profile=='aerial' else .82)
        coverage={};bay_reports=[]
        for slot in cfg.data['slots']:
            sid=slot['id'];poly=validate_polygon(slot['polygon'],width,height)
            assert slot['polygon']==next(s['polygon'] for s in recipe['slots'] if s['id']==sid)
            c=slot.get('calibration',{});m=mog['slots'][sid]
            ref_ok=analyzer._calibration_valid(slot)
            ref_error=analyzer.reference_errors.get(sid)
            assert ref_error in (None,'missing_empty_reference')
            status='calibrated' if ref_ok and m['status']=='calibrated' else 'no_reference' if ref_error else 'empty_only'
            coverage[sid]=status
            row=next(x for x in last['rows'] if x['slot_id']==sid)
            sequence=[(x['recording_id'],x['reference']['sample_time_seconds'],next(r for r in x['rows'] if r['slot_id']==sid)) for x in selected]
            hits=raw[sid];score=max((h['score'] for h in hits if h['unique_bay']),default=None)
            history={}
            for recording_id in sorted({v[0] for v in sequence}):
                series=[v for v in sequence if v[0]==recording_id]
                states=[r['final_state'] for _,_,r in series]
                history[recording_id]=dict(states=states,transitions=sum(a!=b for a,b in zip(states,states[1:])),
                    reasons=dict(Counter(r['yolo_reason'] for _,_,r in series)))
            detail=dict(source=source,slot_id=sid,bay_id=row['bay_id'],polygon_valid=True,
                coverage=status,reference_path=slot.get('reference_image'),reference_error=ref_error,
                reference_calibrated=ref_ok,reference_status=c.get('status'),reference_reason=c.get('reason'),
                mog2_calibrated=m['status']=='calibrated',mog2_reason=m.get('reason'),
                vacant_examples=m['vacant_count'],occupied_examples=m['occupied_count'],
                final_recording=clip_id,final_sample_seconds=last['reference']['sample_time_seconds'],
                reference_state=row['reference_state'],reference_result_reason=row['reference_reason'],
                mog2_state=row['mog2_state'],mog2_result_reason=row['mog2_reason'],
                yolo_state=row['yolo_state'],yolo_reason=row['yolo_reason'],final_state=row['final_state'],
                best_unique_vehicle_score=score,vehicle_candidates=hits,
                model_input_polygon_size=(np.ptp(poly,axis=0)*640/max(width,height)).tolist(),history=history)
            bay_reports.append(detail)
            flat.append({k:v for k,v in detail.items() if k not in ('history','vehicle_candidates','model_input_polygon_size')})
        counts=Counter(coverage.values())
        cv2.imwrite(str(out/f'{source}-setup.jpg'),image_map(start_image,recipe['slots'],coverage))
        cv2.imwrite(str(out/f'{source}-last.jpg'),image_map(last_image,recipe['slots'],coverage,repeated[0]))
        report['sources'][source]=dict(config=str(cfg.path),recipe=recipe_file,polygons=len(coverage),
            valid_references=len(analyzer.references),both_calibrated=counts['calibrated'],
            reference_only=counts['empty_only'],missing_references=counts['no_reference'],
            polygon_overlaps=overlaps,alignment_failures=sum(x['reference']['analysis_status']!='estimated' for x in selected),
            yolo_inference_errors=sum(bool(x['yolo']['error']) for x in selected),
            same_frame_three_runs_identical=True,saved_yolo_states_reproduced=True,
            unresolved_last_reasons=dict(Counter(r['yolo_reason'] for r in last['rows'] if r['final_state'] in ('uncertain','unknown'))),
            bay_reports=bay_reports)
        print(source,dict(counts),'polygons over 1% overlap:',len(overlaps),'repeated inference identical',flush=True)
    overhead_slots=json.loads((ROOT/'presets/overhead-all-bays.json').read_text())['slots']
    adjusted=deepcopy(overhead_slots)
    for slot in adjusted:
        if slot['id']=='WR07':slot['polygon'][2][1]=slot['polygon'][3][1]=428
    timelines=[];changes=0
    for item in [i for i in items if i['recording_id']=='overhead-1']:
        detections=item['yolo']['detections'];targets=set(item['yolo']['requested_slot_ids'])
        before=associate(overhead_slots,detections,targets,.5)
        after=associate(adjusted,detections,targets,.5)
        changes+=sum(a['state']!=b['state'] for a,b in zip(before,after))
        candidates=bay_candidates(overhead_slots,detections,.5)
        for sid in ['WL06','WL11','WR10','ML05','ML10','EL05','ER05','ER08','ER11']:
            score=max((h['score'] for h in candidates[sid] if h['unique_bay']),default=None)
            row=next(r for r in item['rows'] if r['slot_id']==sid)
            timelines.append(dict(slot_id=sid,time=item['reference']['sample_time_seconds'],best_score=score,
                yolo=row['yolo_state'],final=row['final_state']))
    report['overhead_score_timelines']=timelines
    report['minor_overlap_counterfactual']=dict(only_in_memory=True,slot='WR07',bottom_y=428,
        sampled_frames=10,yolo_state_changes=changes)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'per-bay.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    print(json.dumps(report['original_three_bays']),flush=True)
    print(str(out),flush=True)


if __name__=='__main__':main()
