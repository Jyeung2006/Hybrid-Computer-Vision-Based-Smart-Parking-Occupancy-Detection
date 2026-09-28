"""Selective YOLOv8s verification. Missing detections never establish vacancy."""
from concurrent.futures import Future, TimeoutError
from copy import deepcopy
import hashlib
import json
import queue
import threading
import time

import cv2
import numpy as np

from .catalog import PROJECT_ROOT
from .sources import SourceError, utcnow
from .vision import occupancy_summary

MODEL_DIRECTORY = PROJECT_ROOT / 'assets/models'
OCCUPIED_THRESHOLD = .80
MIN_OVERLAP = .25
DECISION_POLICY = 'definite_opencv_agreement_else_yolov8_vehicle_else_unresolved_v2'


def needs_verification(reference, mog2):
    return not (reference == mog2 and reference in ('occupied','vacant'))


def final_decision(reference, mog2, verified):
    """Final states require the displayed branches, never an empty-image override."""
    if not needs_verification(reference,mog2):
        return reference, 'opencv_branches_agree'
    if verified == 'occupied':
        return 'occupied', 'yolov8_verified_vehicle'
    if reference == mog2 == verified == 'unknown':
        return 'unknown', 'no_usable_evidence'
    return 'uncertain', 'yolov8_did_not_resolve_occupancy'


def letterbox(image, size=640):
    h,w = image.shape[:2]
    scale = min(size/w,size/h)
    rw,rh = round(w*scale),round(h*scale)
    left,top = (size-rw)//2,(size-rh)//2
    canvas = np.full((size,size,3),114,np.uint8)
    canvas[top:top+rh,left:left+rw] = cv2.resize(image,(rw,rh),interpolation=cv2.INTER_LINEAR)
    return canvas,scale,left,top


class YOLODetector:
    """Two fixed view profiles, one 640x640 full-frame pass per requested frame."""
    def __init__(self, directory=MODEL_DIRECTORY):
        manifest = json.loads((directory/'yolov8s-manifest.json').read_text())
        self.profiles = manifest['profiles']
        self.nets = {}
        for key,info in self.profiles.items():
            path = directory/info['file']
            if not path.exists() or path.stat().st_size != info['size'] or hashlib.sha256(path.read_bytes()).hexdigest() != info['sha256']:
                raise SourceError('yolov8_model_missing_or_integrity_failed')
            net = cv2.dnn.readNetFromONNX(str(path))
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.nets[key] = net

    def detect(self, image, profile='coco'):
        info = self.profiles[profile]
        net = self.nets[profile]
        canvas,scale,left,top = letterbox(image)
        net.setInput(cv2.dnn.blobFromImage(canvas,1/255,(640,640),swapRB=True,crop=False))
        raw = net.forward()
        if raw.shape != (1,4+info['class_count'],8400) or not np.isfinite(raw).all():
            raise SourceError('yolov8_invalid_output')
        classes = {int(k):v for k,v in info['vehicle_classes'].items()}
        boxes,scores,labels = [],[],[]
        h,w = image.shape[:2]
        for row in raw[0].T:
            label = int(np.argmax(row[4:]))
            score = float(row[4+label])
            if label not in classes or score < .15:
                continue
            cx,cy,bw,bh = map(float,row[:4])
            x1,y1 = max(0,(cx-bw/2-left)/scale),max(0,(cy-bh/2-top)/scale)
            x2,y2 = min(w-1,(cx+bw/2-left)/scale),min(h-1,(cy+bh/2-top)/scale)
            if x2-x1 < 3 or y2-y1 < 3:
                continue
            boxes.append([x1,y1,x2-x1,y2-y1]);scores.append(score);labels.append(classes[label])
        keep = np.asarray(cv2.dnn.NMSBoxes(boxes,scores,.15,.45)).reshape(-1) if boxes else []
        return [{'box':[boxes[i][0],boxes[i][1],boxes[i][0]+boxes[i][2],boxes[i][1]+boxes[i][3]],
                 'detector_score':scores[i],'class':labels[i]} for i in keep]


def associate(slots, detections, requested, anchor_fraction=.82):
    assigned = {s['id']:[] for s in slots}
    touched = {s['id']:False for s in slots}
    for detection in detections:
        x1,y1,x2,y2 = detection['box']
        rectangle = np.float32([[x1,y1],[x2,y1],[x2,y2],[x1,y2]])
        anchor = ((x1+x2)/2,y1+anchor_fraction*(y2-y1))
        candidates=[]
        for slot in slots:  # Include settled neighbours to prevent misassignment.
            polygon=np.float32(slot['polygon'])
            overlap,_=cv2.intersectConvexConvex(polygon,rectangle)
            cover=overlap/abs(cv2.contourArea(polygon))
            if cover >= .1:
                touched[slot['id']]=True
            if cover >= MIN_OVERLAP and cv2.pointPolygonTest(polygon,anchor,True)>=0:
                candidates.append(slot['id'])
        if len(candidates)==1 and detection['detector_score'] >= OCCUPIED_THRESHOLD:
            assigned[candidates[0]].append(detection)
    rows=[]
    for slot in slots:
        key=slot['id'];hits=assigned[key]
        if key not in requested:
            state,reason='unknown','not_requested_opencv_agreement'
        elif slot.get('visibility')=='occluded':
            state,reason='unknown','bay_not_visible_in_this_view'
        elif hits:
            state,reason='occupied','qualifying_yolov8_vehicle_in_unique_bay'
        else:
            state,reason='uncertain',('weak_or_ambiguous_yolov8_vehicle' if touched[key] else 'no_qualifying_detection_is_not_vacancy')
        rows.append({'slot_id':key,'state':state,'reason':reason,'requested':key in requested,
                     'detector_score':max((h['detector_score'] for h in hits),default=None),
                     'matched_vehicle_count':len(hits) if key in requested else 0})
    return rows


class VerificationService:
    """One worker and at most one waiting frame. Expired/superseded jobs are rejected."""
    def __init__(self, detector):
        self.detector=detector
        self.jobs=queue.Queue(maxsize=1)
        self.lock=threading.Lock()
        self.latest={}
        self.closed=threading.Event()
        self.worker=threading.Thread(target=self._work,daemon=True,name='yolov8-verifier')
        self.worker.start()

    def submit(self, image, camera_id, frame_id, slot_ids, profile='coco'):
        future=Future();token=object()
        job={'image':image,'camera_id':camera_id,'frame_id':frame_id,'slot_ids':tuple(slot_ids),
             'profile':profile,'enqueued':time.perf_counter(),'future':future,'token':token}
        with self.lock:
            if self.closed.is_set():
                future.set_result({'error':'yolov8_worker_closed'});return future
            try:self.jobs.put_nowait(job)
            except queue.Full:
                future.set_result({'error':'yolov8_queue_full'});return future
            self.latest[camera_id]=token
        return future

    def _work(self):
        while not self.closed.is_set():
            try:job=self.jobs.get(timeout=.1)
            except queue.Empty:continue
            future=job['future'];started=time.perf_counter()
            with self.lock:current=self.latest.get(job['camera_id']) is job['token']
            if future.cancelled():
                self.jobs.task_done();continue
            try:
                if not current:result={'error':'yolov8_result_superseded'}
                elif self.detector is None:result={'error':'yolov8_model_unavailable'}
                else:result={'detections':self.detector.detect(job['image'],job['profile']),'error':None}
            except Exception:result={'error':'yolov8_worker_failed'}
            with self.lock:
                if self.latest.get(job['camera_id']) is not job['token']:
                    result={'error':'yolov8_result_superseded'}
            result.update(camera_id=job['camera_id'],frame_id=job['frame_id'],slot_ids=list(job['slot_ids']),
                          queue_wait_ms=(started-job['enqueued'])*1000,inference_ms=(time.perf_counter()-started)*1000)
            try:future.set_result(result)
            except Exception:pass  # Caller expired/cancelled; never apply a late result.
            self.jobs.task_done()

    def verify(self, image, camera_id, frame_id, slot_ids, profile='coco', timeout=5):
        future=self.submit(image,camera_id,frame_id,slot_ids,profile)
        try:return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            return {'error':'yolov8_verification_timeout'}

    def close(self):
        self.closed.set()
        while True:
            try:job=self.jobs.get_nowait()
            except queue.Empty:break
            job['future'].cancel();self.jobs.task_done()
        self.worker.join(timeout=.2)


class YOLOBranch:
    def __init__(self, analyzer, service, profile='coco'):
        self.analyzer,self.service,self.profile=analyzer,service,profile

    def analyze(self,image,reference,mog2,requested_slots=None):
        start=time.perf_counter();started=utcnow().isoformat()
        if any(reference.get(k)!=mog2.get(k) for k in ('source_id','frame_id')):
            raise SourceError('yolov8_branch_frame_mismatch')
        other={s['slot_id']:s for s in mog2['slots']}
        targets=([s['slot_id'] for s in reference['slots'] if needs_verification(s['state'],other[s['slot_id']]['state'])]
                 if requested_slots is None else
                 [s['slot_id'] for s in reference['slots'] if s['slot_id'] in requested_slots])
        result=deepcopy(reference);detections=[];job={};error=None
        invalid=reference.get('stale') or reference.get('analysis_status')!='estimated' or image is None
        if invalid:error=reference.get('error') or 'yolov8_frame_unusable'
        elif targets:
            if self.service is None:error='yolov8_model_unavailable'
            else:
                job=self.service.verify(image,reference['source_id'],reference['frame_id'],targets,self.profile)
                error=job.get('error')
                if not error and (job.get('camera_id')!=reference['source_id'] or job.get('frame_id')!=reference['frame_id'] or job.get('slot_ids')!=targets):
                    error='yolov8_result_identity_mismatch'
                if not error:detections=job['detections']
        if error:
            slots=[{'slot_id':s['id'],'state':'unknown','reason':error if s['id'] in targets else 'not_requested_opencv_agreement',
                    'requested':s['id'] in targets,'detector_score':None,'matched_vehicle_count':0} for s in self.analyzer.slot_config]
        else:slots=associate(self.analyzer.slot_config,detections,set(targets),.5 if self.profile=='aerial' else .82)
        result.update(method='selective_yolov8s_verification',slots=slots,summary=occupancy_summary(slots,available=not error),
            detections=detections,requested_slot_ids=targets,inference_requested=bool(targets) and not invalid,
            inference_completed=bool(targets) and not error,skipped_slot_count=len(slots)-len(targets),
            model_profile=self.profile,model_name='YOLOv8s',input_size=640,confidence_threshold=OCCUPIED_THRESHOLD,
            overlap_threshold=MIN_OVERLAP,queue_wait_ms=job.get('queue_wait_ms'),inference_ms=job.get('inference_ms'),
            processing_started_at=started,processed_at=utcnow().isoformat(),processing_duration_ms=(time.perf_counter()-start)*1000,
            error=error,analysis_status='unavailable' if error else 'estimated',
            score_note='Object confidence is not calibrated parking occupancy probability.',
            scope_note='Only requested slots are verified; no detection remains uncertain, never vacant.')
        return result
