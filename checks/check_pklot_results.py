"""Audit saved observations/metrics and protected assets without new inference."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from parking_probe.config import atomic_json
from parking_probe.pklot import sha256
from parking_probe.pklot_evaluation import verify_frozen, select_profile
from parking_probe.yolo import needs_verification, final_decision


def main():
    cache=ROOT/'data/pklot'
    output=ROOT/'runs/verification/pklot'
    report=json.loads((output/'evaluation.json').read_text())
    public=json.loads((ROOT/'runs/verification/pklot-evaluation.json').read_text())
    assert report==public
    frozen=verify_frozen(cache,output)
    assert report['frozen_sha256']==sha256(output/'frozen.json')
    assert report['selected_profile']==frozen['selected_profile']==select_profile(report['calibrate'])
    assert json.loads((output/'test-started.json').read_text())['frozen_sha256']==report['frozen_sha256']
    manifest=json.loads((cache/'partitions.json').read_text())
    date_sets={phase:{r['day'] for r in rows} for phase,rows in manifest['partitions'].items()}
    assert len(set.union(*date_sets.values()))==sum(map(len,date_sets.values()))==30
    assert list(map(len,date_sets.values()))==[18,6,6]
    protected=json.loads((ROOT/'runs/verification/pklot-protected-before.json').read_text())
    changed=[name for name,d in protected.items() if sha256(ROOT/name)!=d]
    assert not changed, changed
    all_pixels=set(json.loads((cache/'experiment/fit.json').read_text())['fit_pixel_hashes'])
    totals={}
    for phase in ('calibrate','test'):
        entries={r['frame_id']:r for r in manifest['partitions'][phase]}
        seen=set(); counts=Counter(); label_count=decisions=0
        for path in sorted((output/phase).glob('*.json')):
            day=json.loads(path.read_text())
            expected_identity=frozen['calibrate_identity'] if phase=='calibrate' else report['frozen_sha256']
            assert day['identity']==expected_identity
            assert not all_pixels.intersection(day['pixel_hashes'])
            assert len(day['pixel_hashes'])==len(set(day['pixel_hashes']))
            all_pixels.update(day['pixel_hashes'])
            assert day['frame_ids']==[f['frame_id'] for f in day['frames']]
            for frame in day['frames']:
                key=frame['frame_id']; assert key not in seen;seen.add(key)
                original=entries[key]
                assert frame['weather']==original['weather']
                assert {r['slot_id']:r['truth'] for r in frame['observations']}==original['labels']
                for row in frame['observations']:
                    label_count+=1
                    s=row['states']
                    for profile in ('coco','aerial'):
                        expected=needs_verification(s['reference'],s['mog2'])
                        assert row['requested'][profile]==expected
                        state,reason=final_decision(s['reference'],s['mog2'],s['yolo_'+profile])
                        assert s['final_'+profile]==state and row['reasons']['final_'+profile]==reason
                        if state=='vacant':assert s['reference']==s['mog2']=='vacant'
                    for method,state in s.items():
                        assert state in ('occupied','vacant','uncertain','unknown')
                        for weather in ('all',frame['weather']):
                            counts[method,weather,row['truth'],state]+=1
                    if frame['alignment_error']:
                        assert all(v=='unknown' for v in s.values())
                    decisions+=1
        assert seen==set(entries)
        assert len(seen)==report[phase]['frames']
        assert label_count==report[phase]['labelled_observations']==manifest['summary'][phase]['labelled_observations']
        for method,strata in report[phase]['methods'].items():
            if method.endswith('_requested_only'):continue
            for weather in ('all','sunny','cloudy','rainy'):
                m=strata[weather]
                for truth,cells in m['confusion_matrix'].items():
                    for state,n in cells.items():assert n==counts[method,weather,truth,state]
                tp,tn,fn,fp=(m['confusion'][k] for k in ('true_occupied','true_vacant','false_vacant','false_occupied'))
                classified=tp+tn+fn+fp
                assert m['classified_observations']==classified
                assert m['unresolved_observations']+classified==m['binary_observations']
                ratios={'accuracy_on_classified_pct':(tp+tn,classified),
                    'precision_on_classified_pct':(tp,tp+fp),'recall_on_classified_pct':(tp,tp+fn),
                    'f1_on_classified_pct':(2*tp,2*tp+fp+fn),'decision_coverage_pct':(classified,m['binary_observations']),
                    'false_vacant_rate_all_occupied_pct':(fn,m['ground_truth_counts']['occupied']),
                    'false_occupied_rate_all_vacant_pct':(fp,m['ground_truth_counts']['vacant'])}
                for name,(numerator,denominator) in ratios.items():
                    expected=100*numerator/denominator if denominator else None
                    assert m[name]==expected
        totals[phase]={'frames':len(seen),'labelled_observations':label_count,'decision_policy_checks':decisions*2}
    audit={'status':'passed','protected_files_unchanged':len(protected),'phases':totals,
        'frozen_sha256':report['frozen_sha256'],'selected_profile':report['selected_profile'],
        'checks':['day partition disjointness','exact truth/frame identity','decoded-content leakage',
            'selective trigger and final policy','alignment failures abstain','all/weather matrices and metric arithmetic',
            'frozen code/config/runtime/model manifest','protected CHAD/overhead asset hashes'],
        'no_new_inference':True}
    atomic_json(ROOT/'runs/verification/pklot-delivery-check.json',audit)
    print(json.dumps(audit,indent=2))


if __name__=='__main__':
    main()
