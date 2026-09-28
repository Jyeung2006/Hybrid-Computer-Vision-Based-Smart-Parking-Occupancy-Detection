"""Per-bay OpenCV-first selection for the recorded parking review."""

DEFINITE = ('occupied', 'vacant')
DECISION_POLICY = 'opencv_first_mobilenet_then_selective_yolov8_v1'


def before_yolo(reference, mog2, mobilenet):
    """Return state, reason, source, and whether this bay needs YOLO."""
    ref_ok, mog_ok = reference in DEFINITE, mog2 in DEFINITE
    if ref_ok and mog_ok:
        if reference == mog2:
            return reference, 'opencv_branches_agree', 'reference_and_mog2', False
        return 'uncertain', 'opencv_definite_conflict', None, True
    if ref_ok:
        return reference, 'reference_definite_mog2_unresolved', 'reference', False
    if mog_ok:
        return mog2, 'mog2_definite_reference_unresolved', 'mog2', False
    if mobilenet in DEFINITE:
        source = ('mobilenet_reviewed_empty' if mobilenet == 'vacant' else 'mobilenet_ssd')
        return mobilenet, 'mobilenet_' + mobilenet, source, False
    return 'uncertain', 'all_opencv_unresolved', None, True


def after_yolo(reference, mog2, mobilenet, verified):
    state, reason, source, requested = before_yolo(reference, mog2, mobilenet)
    if not requested:
        return state, reason, source
    if verified == 'occupied':
        return 'occupied', 'yolov8_verified_vehicle', 'yolov8'
    if reference in DEFINITE and mog2 in DEFINITE and reference != mog2:
        return reference, 'reference_after_yolov8_conflict_check', 'reference'
    return 'uncertain', 'opencv_and_yolov8_unresolved', None


def provisional_occupied_allowed(reference_result, mog2_result, yolo_result,
                                 image, slot, yolo_slot):
    """Never guess occupied for a stale, occluded or unverified sample."""
    return (image is not None
            and reference_result.get('analysis_status') == 'estimated'
            and reference_result.get('stale') is False
            and reference_result.get('error') is None
            and (reference_result.get('alignment') or {}).get('ok') is True
            and mog2_result.get('analysis_status') == 'estimated'
            and not mog2_result.get('error')
            and yolo_result.get('inference_completed') is True
            and not yolo_result.get('error')
            and slot.get('visibility') != 'occluded'
            and yolo_slot.get('requested') is True
            and yolo_slot.get('state') == 'uncertain')
