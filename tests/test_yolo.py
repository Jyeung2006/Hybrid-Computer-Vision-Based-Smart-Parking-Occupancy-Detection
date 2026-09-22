import threading
from copy import deepcopy
import numpy as np
import pytest
from parking_probe.yolo import (needs_verification,final_decision,associate,letterbox,
    YOLOBranch,VerificationService)
from parking_probe.vision import Analyzer
from parking_probe.sources import Frame,utcnow

SLOTS=[{'id':'A','polygon':[[10,10],[90,10],[90,90],[10,90]]},
       {'id':'B','polygon':[[100,10],[180,10],[180,90],[100,90]]}]


@pytest.mark.parametrize('ref', ['vacant','occupied','uncertain','unknown'])
@pytest.mark.parametrize('mog', ['vacant','occupied','uncertain','unknown'])
@pytest.mark.parametrize('verified', ['vacant','occupied','uncertain','unknown'])
def test_every_definite_final_has_visible_method_confirmation(ref, mog, verified):
    state, reason = final_decision(ref, mog, verified)
    if ref == mog and ref in ('occupied','vacant'):
        assert (state, reason) == (ref, 'opencv_branches_agree')
    elif verified == 'occupied':
        assert (state, reason) == ('occupied', 'yolov8_verified_vehicle')
    else:
        assert state in ('uncertain','unknown')
    if state == 'vacant':
        assert ref == mog == 'vacant'


@pytest.mark.parametrize('ref,mog,requested',[
 ('occupied','occupied',False),('vacant','vacant',False),
 ('occupied','vacant',True),('vacant','occupied',True),
 ('occupied','uncertain',True),('uncertain','vacant',True),
 ('uncertain','uncertain',True),('unknown','occupied',True),('unknown','unknown',True)])
def test_requested_truth_table(ref,mog,requested):
    assert needs_verification(ref,mog) is requested
    state,_=final_decision(ref,mog,'occupied')
    assert state == (ref if not requested else 'occupied')


@pytest.mark.parametrize('score,state',[(.799999,'uncertain'),(.8,'occupied'),(.800001,'occupied')])
def test_confidence_boundary(score,state):
    rows=associate(SLOTS,[{'box':[20,20,80,80],'detector_score':score}],{'A','B'},.5)
    assert rows[0]['state']==state
    assert rows[1]['state']=='uncertain'  # A missed box is never a vacant candidate.


def test_ambiguity_and_settled_slots_are_not_overwritten():
    overlapping=[SLOTS[0],{**SLOTS[1],'polygon':SLOTS[0]['polygon']}]
    assert all(r['state']=='uncertain' for r in associate(overlapping,[{'box':[20,20,80,80],'detector_score':.9}],{'A','B'},.5))
    rows=associate(SLOTS,[{'box':[20,20,80,80],'detector_score':.9}],{'B'},.5)
    assert rows[0]['state']=='unknown' and not rows[0]['requested']
    assert final_decision('vacant','vacant','occupied')==('vacant','opencv_branches_agree')
    assert final_decision('occupied','vacant','uncertain')[0]=='uncertain'
    assert final_decision('unknown','unknown','unknown')[0]=='unknown'


def test_letterbox_retains_aspect_ratio_and_padding():
    image=np.full((100,200,3),255,np.uint8)
    out,scale,left,top=letterbox(image)
    assert out.shape==(640,640,3) and scale==3.2 and left==0 and top==160
    assert np.all(out[:160]==114) and np.all(out[160:480]==255)


def test_worker_one_pending_frame_and_superseded_result():
    entered,release=threading.Event(),threading.Event()
    class Slow:
        def detect(self,image,profile):entered.set();release.wait(2);return []
    service=VerificationService(Slow())
    try:
        first=service.submit(None,'cam','first',['A']);assert entered.wait(1)
        second=service.submit(None,'cam','second',['A'])
        rejected=service.submit(None,'other','third',['B'])
        assert rejected.result(1)['error']=='yolov8_queue_full'
        release.set()
        assert first.result(1)['error']=='yolov8_result_superseded'
        assert second.result(1)['frame_id']=='second'
        assert second.result()['error'] is None
    finally:release.set();service.close()


def test_worker_failure_timeout_and_close_are_explicit():
    class Broken:
        def detect(self,image,profile):raise RuntimeError('private provider detail')
    service=VerificationService(Broken())
    assert service.verify(None,'cam','f',['A'])['error']=='yolov8_worker_failed'
    service.close()
    assert service.submit(None,'cam','f',['A']).result()['error']=='yolov8_worker_closed'
    release=threading.Event()
    class Slow:
        def detect(self,image,profile):release.wait(2);return []
    service=VerificationService(Slow())
    try:assert service.verify(None,'cam','f',['A'],timeout=.01)['error']=='yolov8_verification_timeout'
    finally:release.set();service.close()


def test_one_inference_for_multiple_bays_and_zero_for_agreement(config,scene):
    analyzer=Analyzer(config);checked=analyzer.analyze(Frame(scene[2](1),utcnow()))
    ref=deepcopy(checked);mog=deepcopy(checked)
    class Counting:
        calls=0
        def verify(self,image,camera,frame,slots,profile):
            self.calls+=1
            return {'camera_id':camera,'frame_id':frame,'slot_ids':slots,'detections':[],'error':None}
    service=Counting();branch=YOLOBranch(analyzer,service)
    for s in ref['slots']:s['state']='uncertain'
    for s in mog['slots']:s['state']='vacant'
    result=branch.analyze(scene[2](1),ref,mog)
    assert service.calls==1 and len(result['requested_slot_ids'])==len(ref['slots'])
    assert all(s['state']=='uncertain' for s in result['slots'])
    for s in ref['slots']:s['state']='vacant'
    result=branch.analyze(scene[2](1),ref,mog)
    assert service.calls==1 and not result['inference_requested']
    assert all(not s['requested'] for s in result['slots'])
    ref['stale']=True
    result=branch.analyze(scene[2](1),ref,mog)
    assert service.calls==1 and result['error']=='yolov8_frame_unusable'


def test_wrong_frame_response_is_discarded(config,scene):
    analyzer=Analyzer(config);ref=analyzer.analyze(Frame(scene[2](1),utcnow()));mog=deepcopy(ref)
    for s in ref['slots']:s['state']='uncertain'
    class Wrong:
        def verify(self,*args):return {'camera_id':'wrong','error':None,'detections':[]}
    result=YOLOBranch(analyzer,Wrong()).analyze(scene[2](1),ref,mog)
    assert result['error']=='yolov8_result_identity_mismatch'
    assert all(s['state']=='unknown' for s in result['slots'])
