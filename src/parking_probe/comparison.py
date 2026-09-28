"""Replay separate CHAD periods together, reporting both OpenCV branches."""
from datetime import datetime, timezone
from pathlib import Path
import time

import cv2

from .bay_fusion import TimeWindow
from .catalog import PROJECT_ROOT, fetch_clip
from .config import ConfigError, atomic_json
from .display_model import occupancy_text, video_clock
from .mog2 import MOG2Branch
from .mog2_calibration import prepare_mog2
from . import monitor
from .output import Reporter
from .site_replay import SiteReporter
from .sources import Frame, SourceError, utcnow, write_image
from .vision import Analyzer, occupancy_summary
from .yolo import DECISION_POLICY
from .vacancy_guard import GuardedVacancy, GUARDED_DECISION_POLICY
from .opencv_first import (DECISION_POLICY as OPENCV_FIRST_POLICY, before_yolo,
                           after_yolo, provisional_occupied_allowed)

BAY_MAP = {"B01": "CHAD-P001", "B02": "CHAD-P002", "B03": "CHAD-P003"}


def consensus(reference_state, mog2_state):
    if reference_state == mog2_state and reference_state in ("occupied", "vacant"):
        return reference_state
    if reference_state == mog2_state == "unknown":
        return "unknown"
    return "uncertain"


def final_summary(recordings, status):
    rows = [{**row, "final_state": row.get("final_state", consensus(row["reference_state"], row["mog2_state"]))}
            for result in recordings for row in result["rows"]]
    summaries = {}
    for recording in recordings:
        selected = [{"state": r["final_state"]} for r in rows if r["recording_id"] == recording["recording_id"]]
        summary = occupancy_summary(selected, available=any(s["state"] != "unknown" for s in selected))
        for state in ('occupied', 'vacant'):
            summary[f'provisional_{state}'] = sum(r['recording_id'] == recording['recording_id']
                and r['final_state'] == state and bool(r.get('final_provisional')) for r in rows)
        summaries[recording["recording_id"]] = summary
    return {"run_status": status, "generated_at": utcnow().isoformat(), "historical": True,
            "current_occupancy_available": False, "basis": "last_sampled_frame_per_recording",
            "decision_rule": (OPENCV_FIRST_POLICY if any(r.get('decision_policy') == OPENCV_FIRST_POLICY for r in rows) else
                              GUARDED_DECISION_POLICY if any(r.get('decision_policy') == GUARDED_DECISION_POLICY for r in rows) else
                              DECISION_POLICY if any('yolo_state' in r for r in rows) else
                              "vehicle_evidence_fallback; conflicting_definite_methods_stay_uncertain" if any('vehicle_state' in r for r in rows)
                              else "both_methods_agree_else_uncertain; both_unknown_stays_unknown"),
            "rows": rows, "summaries_by_recording": summaries}


def format_final(result):
    lines = ["", "=" * 90, "FINAL HISTORICAL ESTIMATE | Last sampled frame per recording",
             f"{'VIDEO':<8} {'TIME':<7} {'BAY':<11} {'REFERENCE':<11} {'MOG2':<11} FINAL ESTIMATE", "-" * 90]
    for row in result["rows"]:
        lines.append(f"{row['recording_id']:<8} {video_clock(row['video_position_seconds']):<7} {row['bay_id']:<11} "
                     f"{row['reference_state'].upper():<11} {row['mog2_state'].upper():<11} "
                     f"{row['final_state'].upper()}{' (P)' if row.get('final_provisional') else ''}")
    for clip, s in result["summaries_by_recording"].items():
        lines.append(f"{clip}: {s['occupied']} occupied | {s['vacant']} vacant | {s['uncertain']} uncertain | "
                     f"{s['unknown']} unknown | occupancy {occupancy_text(s)}")
    lines.append("Historical estimates for separate periods; no current/live availability or confirmed state is asserted.")
    return "\n".join(lines)


def window_snapshot(result, when, mapping):
    summary = dict(result['summary'])
    for state in ('occupied', 'vacant'):
        summary[f'provisional_{state}'] = sum(s['state'] == state and bool(s.get('provisional'))
                                               for s in result['slots'])
    return {"timeline_seconds": when, "summary": summary,
            "bays": [{"bay_id": mapping[s["slot_id"]], "state": s["state"], "reason": s["reason"],
                      "provisional": s.get('provisional', False),
                      "vacancy_evidence": s.get('vacancy_evidence'),
                      "usable_views": int(s["state"] != "unknown"), "expected_views": 1,
                      "degraded": s["state"] == "unknown"} for s in result["slots"]]}


def join_branches(video_id, reference, mog2):
    for key in ("frame_id", "source_id", "video_frame_index", "sample_time_seconds"):
        if reference.get(key) != mog2.get(key):
            raise ConfigError("Cannot join results from different frames/cameras/times.")
    if {s["slot_id"] for s in reference["slots"]} != {s["slot_id"] for s in mog2["slots"]}:
        raise ConfigError("Cannot join results from different parking polygons.")
    other = {s["slot_id"]: s for s in mog2["slots"]}
    rows = []
    for slot in reference["slots"]:
        m = other[slot["slot_id"]]
        definite = slot["state"] in ("occupied", "vacant") and m["state"] in ("occupied", "vacant")
        rows.append({"recording_id": video_id, "camera_id": reference["source_id"], "bay_id": slot["bay_id"],
                     "slot_id": slot["slot_id"], "frame_id": reference["frame_id"],
                     "sample_time_seconds": reference["sample_time_seconds"], "video_position_seconds": reference["video_position_seconds"],
                     "source_captured_at": reference["source_captured_at"], "processed_at": mog2["processed_at"],
                     "reference_state": slot["state"], "reference_difference": slot["difference_score"],
                     "reference_reason": slot["reason"], "mog2_state": m["state"],
                     "mog2_foreground_ratio": m["foreground_ratio"], "mog2_shadow_ratio": m["shadow_ratio"],
                     "mog2_reason": m["reason"], "reference_ms": reference["processing_duration_ms"],
                     "mog2_ms": mog2["processing_duration_ms"],
                     "agreement": ("agree" if slot["state"] == m["state"] else "disagree") if definite else "unresolved"})
    return {"recording_id": video_id, "camera_id": reference["source_id"], "reference": reference,
            "mog2": mog2, "rows": rows}


def format_samples(batch):
    when = batch["timeline_seconds"]
    lines = ["", f"VIDEO {video_clock(when)} | Processed {batch['display_time']} | Separate recording periods",
             f"{'VIDEO':<8} {'BAY':<11} {'REFERENCE':<11} {'DIFF':>7}  {'MOG2':<11} {'FG %':>7}  AGREEMENT", "-" * 84]
    for result in batch["recordings"]:
        for row in result["rows"]:
            diff = "--" if row["reference_difference"] is None else f"{row['reference_difference']:.3f}"
            fg = "--" if row["mog2_foreground_ratio"] is None else f"{100*row['mog2_foreground_ratio']:.1f}"
            lines.append(f"{row['recording_id']:<8} {row['bay_id']:<11} {row['reference_state'].upper():<11} "
                         f"{diff:>7}  {row['mog2_state'].upper():<11} {fg:>7}  {row['agreement']}")
            if row["reference_state"] == "unknown" or row["mog2_state"] == "unknown" or row["mog2_reason"] in ("mog2_uncalibrated", "mog2_restabilizing_after_gap"):
                lines.append(f"  Details: reference={row['reference_reason'] or 'ok'}; MOG2={row['mog2_reason'] or 'ok'}")
    if batch["ended_recordings"]:
        lines.append("Finished: " + ", ".join(batch["ended_recordings"]) + " (historical results saved)")
    return "\n".join(lines)


def format_comparison_windows(windows):
    def rate(bay):
        low, high = bay["occupied_time_min_pct"], bay["occupied_time_max_pct"]
        return f"{low:.1f}%" if abs(high-low) < 1e-8 else f"{low:.1f}-{high:.1f}%"

    first = windows[0]["reference"]
    kind = "FINAL PARTIAL" if first["partial_window"] else "10-SECOND SUMMARY"
    lines = ["", "=" * 90,
             f"{kind} | {video_clock(first['window_start_seconds'])} - {video_clock(first['window_end_seconds'])} "
             f"| {first['window_duration_seconds']:.3f}s | {windows[0]['display_time']}",
             f"{'VIDEO':<8} {'BAY':<11} {'REF STATE':<11} {'REF OCC. TIME':<15} {'MOG2 STATE':<11} MOG2 OCC. TIME", "-" * 90]
    for window in windows:
        for ref, mog in zip(window["reference"]["bays"], window["mog2"]["bays"], strict=True):
            lines.append(f"{window['recording_id']:<8} {ref['bay_id']:<11} {ref['state'].upper():<11} "
                         f"{rate(ref):<15} {mog['state'].upper():<11} {rate(mog)}")
    lines.extend(["", "Latest counts per recording: occupied / vacant / uncertain / unknown"])
    for window in windows:
        summaries = []
        for method in ("reference", "mog2"):
            s = window[method]["summary"]
            counts = "/".join(str(s[k]) for k in ("occupied", "vacant", "uncertain", "unknown"))
            summaries.append(f"{method.upper()} {counts} ({occupancy_text(s)})")
        lines.append(f"{window['recording_id']:<8} " + " | ".join(summaries))
    lines.append("Occupied time is a window-duration estimate; DIFF and FG are not probabilities.")
    return "\n".join(lines)


def run_comparison(clips, interval, stop, emit, fast=False, frame_limit=0, out=None, prepared=None, bay_map=None,
                   supplemental=False, detector=None, verification=False, service=None, verification_profile='coco',
                   alternate_policy=False, opencv_first=False):
    if opencv_first and not verification:
        raise ConfigError('OpenCV-first selection requires YOLO fallback support.')
    if alternate_policy and not verification:
        raise ConfigError('The alternate comparison requires the existing YOLO verification pipeline.')
    if supplemental and verification:
        raise ConfigError('Choose one verification policy for a run.')
    if frame_limit < 0 or interval <= 0:
        raise ConfigError("Invalid frame limit or sample interval.")
    config, recipe, paths = prepared if prepared is not None else monitor.prepare_preset(emit, stop)
    mapping = BAY_MAP if bay_map is None else bay_map
    if set(mapping) != {s['id'] for s in config.data['slots']} or len(set(mapping.values())) != len(mapping):
        raise ConfigError("A unique physical bay ID is required for each configured polygon.")
    for clip in clips:
        if clip.id not in paths:
            paths[clip.id] = fetch_clip(clip, lambda msg: emit("status", msg), stop.is_set)
    calibration = prepare_mog2(config, recipe, paths, interval, emit, stop)
    analyzer = Analyzer(config)
    vacancy_guard = GuardedVacancy(analyzer, interval, recipe.get('slots'), reviewed_only=opencv_first) if verification else None
    methods = (('reference','mog2','vehicle','yolo','final') if opencv_first else
               ('reference','mog2','yolo','final') if verification else
               ("reference", "mog2", "vehicle", "final") if supplemental else ("reference", "mog2"))
    if verification:
        from .yolo import YOLOBranch, final_decision as selective_decision
        yolo_branch = YOLOBranch(analyzer,service,verification_profile)
    if supplemental or opencv_first:
        from .vehicle import VehicleBranch, final_decision
        vehicle_branch = VehicleBranch(analyzer, detector)
    out = Path(out) if out else PROJECT_ROOT / "runs/comparison" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    store = SiteReporter(out, {"comparison_scope": "separate_recording_periods", "camera_id": config.data["source_id"],
        "recording_ids": [c.id for c in clips], "physical_bay_map": mapping,
        "reference_config": str(config.path), "mog2_signature": calibration["model_signature"]})
    atomic_json(out / "mog2-calibration.json", calibration)
    emit("status", "Results: " + str(out))
    runtimes = {}
    errors, ticks, skipped = 0, 0, 0
    window_count = 0
    status = "preparing"
    position = 0.0
    begun = time.monotonic()

    def publish_windows(ids, when, partial=False):
        nonlocal window_count
        reports = []
        for clip_id in ids:
            runtime = runtimes[clip_id]
            summaries = {m: runtime["windows"][m].close(when, partial) for m in methods}
            ref = summaries['reference']
            if ref is None:
                continue
            now = utcnow()
            report = {"recording_id": clip_id, "generated_at": now.isoformat(), "display_time": now.astimezone().strftime("%H:%M:%S"),
                      **summaries, "late_by_seconds": max(0, time.monotonic()-begun-when) if not fast else None}
            store.append("windows.jsonl", report)
            atomic_json(out / clip_id / "latest-window.json", report)
            common = {"recording_id": clip_id, "generated_at": report["generated_at"], "window_start_seconds": ref["window_start_seconds"],
                      "window_end_seconds": when, "duration_seconds": ref["window_duration_seconds"], "partial_window": partial}
            for method, summary in summaries.items():
                store.csv("summary.csv", [{**common, "method": method, **summary["summary"]}])
                store.csv("bay-windows.csv", [{**common, "method": method, "bay_id": b["bay_id"], "latest_state": b["state"],
                    "provisional": bool(b.get('provisional')),
                    "occupied_time_min_pct": b["occupied_time_min_pct"], "occupied_time_max_pct": b["occupied_time_max_pct"],
                    "classified_time_pct": b["classified_time_pct"], **{f"{s}_seconds": v for s,v in b["state_seconds"].items()}}
                    for b in summary["bays"]])
            reports.append(report)
            window_count += 1
        if reports:
            emit("comparison_windows", reports)

    try:
        for clip in clips:
            recording = monitor.recording_for_recipe(paths[clip.id], recipe)
            initial = window_snapshot(analyzer.failure("not_started"), 0, mapping)
            runtimes[clip.id] = {"clip": clip, "recording": recording, "ended": False,
                "mog2": MOG2Branch(analyzer, calibration, interval), "samples": 0, "last": None,
                "windows": {m: TimeWindow(initial) for m in methods},
                "reporters": {m: Reporter(out / clip.id / m, config.data["slots"]) for m in methods}}
        if not runtimes:
            raise ConfigError("Select at least one recording.")
        begun = time.monotonic()
        next_sample, next_window = 0.0, 10.0
        status = "complete"
        while any(not r["ended"] for r in runtimes.values()):
            active = [key for key, r in runtimes.items() if not r["ended"]]
            when = min(next_sample, next_window, min(runtimes[k]["recording"].duration for k in active))
            if stop.is_set() or (not fast and stop.wait(max(0, begun + when - time.monotonic()))):
                status = "stopped"
                break
            position = when
            if abs(when-next_window) < 1e-8:
                publish_windows(active, when)
                next_window += 10
            ending = [k for k in active if when >= runtimes[k]["recording"].duration]
            if ending:
                publish_windows(ending, when, partial=True)
                for key in ending:
                    runtimes[key]["ended"] = True
                    emit("status", f"{key} finished at video {when:.3f}s; recording history saved.")
            if not any(not runtimes[k]["ended"] for k in active):
                continue
            if abs(when-next_sample) >= 1e-8:
                continue
            overdue = not fast and time.monotonic()-begun-when >= interval
            skipped += int(overdue)
            batch = {"timeline_seconds": when, "display_time": datetime.now().astimezone().strftime("%H:%M:%S"),
                     "recordings": [], "ended_recordings": [k for k,r in runtimes.items() if r["ended"]]}
            for clip_id in active:
                runtime = runtimes[clip_id]
                if runtime["ended"]:
                    continue
                recording = runtime["recording"]
                index = min(round(when * recording.fps), recording.count-1)
                image = None
                try:
                    if overdue:
                        raise SourceError("replay_sample_missed")
                    start = time.perf_counter()
                    image = recording.read(index)
                    decode_ms = (time.perf_counter()-start)*1000
                    frame = Frame(image, utcnow(), frame_id=f"{clip_id}-{index:06d}")
                    reference = analyzer.analyze(frame)
                    if getattr(recording,'registration',None):
                        reference['registration'] = recording.registration
                        valid = recording.stabilizer.valid_mask
                        if any((valid[mask!=0] == 0).any() for mask in analyzer.masks.values()):
                            raise SourceError('registered_bay_outside_visible_frame')
                    reference["retrieval_duration_ms"] = decode_ms
                    try:
                        mog = runtime["mog2"].analyze(frame, index/recording.fps, reference)
                    except (RuntimeError, OSError, cv2.error):
                        # A branch failure must not erase valid evidence from
                        # the other branch or carry partially updated state.
                        runtime["mog2"].needs_reset = True
                        mog = runtime["mog2"].failure(reference, "mog2_processing_failed")
                        errors += 1
                except (SourceError, RuntimeError, OSError, cv2.error) as exc:
                    reason = str(exc) if isinstance(exc, SourceError) else "recorded_video_decode_failed"
                    reference = analyzer.failure(reason)
                    mog = runtime["mog2"].failure(reference, reason)
                    image = None
                    errors += int(not overdue)
                for method, result in (("reference", reference), ("mog2", mog)):
                    result.update({"input_mode": "recorded_video", "monitoring_scope": "monitored_bays", "video_id": clip_id,
                        "video_filename": runtime["clip"].member, "video_sha256": runtime["clip"].sha256,
                        "sample_time_seconds": when, "video_position_seconds": index/recording.fps, "video_frame_index": index,
                        "video_duration_seconds": recording.duration, "original_capture_time_known": False,
                        "freshness_basis": "local_recorded_frame_decode", "update_interval_seconds": interval,
                        "replay_elapsed_seconds": time.monotonic()-begun})
                    for slot in result["slots"]:
                        slot["bay_id"] = mapping[slot["slot_id"]]
                    runtime["reporters"][method].write(result, image)
                    runtime["windows"][method].update(when, window_snapshot(result, when, mapping))
                if runtime["mog2"].clean_mask is not None:
                    write_image(out / clip_id / "mog2/foreground.png", cv2.cvtColor(runtime["mog2"].clean_mask, cv2.COLOR_GRAY2BGR))
                elif (out / clip_id / "mog2/foreground.png").exists():
                    (out / clip_id / "mog2/foreground.png").unlink()
                joined = join_branches(clip_id, reference, mog)
                for row in joined['rows']:
                    # Provenance for later opt-in derivation; this never changes a decision.
                    row['reference_calibrated'] = analyzer._calibration_valid(config.slot(row['slot_id']))
                if opencv_first:
                    vehicle = vehicle_branch.analyze(image, reference)
                    vehicle_slots = {s['slot_id']: s for s in vehicle['slots']}
                    targets = set()
                    for row in joined['rows']:
                        evidence = vehicle_slots[row['slot_id']]
                        evidence['bay_id'] = row['bay_id']
                        row.update(vehicle_state=evidence['state'], vehicle_reason=evidence['reason'],
                                   vehicle_detector_score=evidence['detector_score'],
                                   vehicle_empty_difference=evidence['empty_difference'],
                                   vehicle_empty_limit=evidence['empty_match_limit'],
                                   vehicle_ms=vehicle['processing_duration_ms'])
                        if before_yolo(row['reference_state'], row['mog2_state'], evidence['state'])[3]:
                            targets.add(row['slot_id'])
                    runtime['reporters']['vehicle'].write(vehicle, image)
                    runtime['windows']['vehicle'].update(when, window_snapshot(vehicle, when, mapping))
                    joined['vehicle'] = vehicle
                if verification:
                    yolo = (yolo_branch.analyze(image,reference,mog,targets) if opencv_first else
                            yolo_branch.analyze(image,reference,mog))
                    completed_at = utcnow().isoformat()
                    by_slot = {s['slot_id']:s for s in yolo['slots']}
                    for row in joined['rows']:
                        evidence=by_slot[row['slot_id']]
                        evidence['bay_id']=row['bay_id']
                        if opencv_first:
                            state,reason,confirmed_by = after_yolo(row['reference_state'],row['mog2_state'],
                                                                   row['vehicle_state'],evidence['state'])
                        else:
                            state,reason=selective_decision(row['reference_state'],row['mog2_state'],evidence['state'])
                            confirmed_by = {'opencv_branches_agree':'reference_and_mog2',
                                'yolov8_verified_vehicle':'yolov8'}.get(reason)
                        row.update(yolo_state=evidence['state'],yolo_reason=evidence['reason'],yolo_requested=evidence['requested'],
                            yolo_detector_score=evidence['detector_score'],yolo_ms=yolo['processing_duration_ms'],
                            yolo_profile=verification_profile,final_state=state,final_reason=reason,processed_at=completed_at,
                            final_confirmed_by=confirmed_by,decision_policy=DECISION_POLICY)
                    guard_started = time.perf_counter()
                    vacancy_guard.apply(clip_id, when, reference, mog, yolo, image, joined['rows'])
                    if opencv_first:
                        by_config = {s['id']: s for s in analyzer.slot_config}
                        for row in joined['rows']:
                            row['decision_policy'] = OPENCV_FIRST_POLICY
                            row['pre_guard_fallback_state'] = None
                            row['pre_guard_fallback_reason'] = None
                            if row['base_final_reason'] != 'opencv_and_yolov8_unresolved':
                                continue
                            can_guess = provisional_occupied_allowed(reference, mog, yolo, image,
                                by_config[row['slot_id']], by_slot[row['slot_id']])
                            if can_guess:
                                row['pre_guard_fallback_state'] = 'occupied'
                                row['pre_guard_fallback_reason'] = 'provisional_occupied_no_definite_evidence'
                                if row['final_state'] not in ('occupied', 'vacant'):
                                    row.update(final_state='occupied', final_reason='provisional_occupied_no_definite_evidence',
                                               final_confirmed_by=None, final_provisional=True)
                            elif row['final_state'] not in ('occupied', 'vacant'):
                                row.update(final_state='unknown', final_reason='analysis_or_verification_unavailable',
                                           final_confirmed_by=None, final_provisional=False)
                    guard_ms = (time.perf_counter()-guard_started)*1000
                    completed_at = utcnow().isoformat()
                    final_slots=[{'slot_id':row['slot_id'],'bay_id':row['bay_id'],'state':row['final_state'],
                        'reason':row['final_reason'],'confirmed_by':row['final_confirmed_by'],
                        'provisional':row['final_provisional'], 'vacancy_evidence':row['vacancy_evidence'],
                        'vacancy_guard_streak':row['vacancy_guard_streak']}
                        for row in joined['rows']]
                    for row in joined['rows']:
                        row['processed_at'] = completed_at
                        row['guard_processing_ms'] = guard_ms
                    final_result={**reference,'method':'opencv_first_final_estimate' if opencv_first else 'selective_yolov8_final_estimate','slots':final_slots,
                        'summary':occupancy_summary(final_slots,available=any(s['state']!='unknown' for s in final_slots)),
                        'processed_at':completed_at,'decision_policy':OPENCV_FIRST_POLICY if opencv_first else GUARDED_DECISION_POLICY,
                        'provisional_vacant_count':sum(s['provisional'] and s['state']=='vacant' for s in final_slots),
                        'provisional_occupied_count':sum(s['provisional'] and s['state']=='occupied' for s in final_slots),
                        'guard_processing_duration_ms':guard_ms,
                        'processing_duration_ms':sum((r.get('processing_duration_ms') or 0) for r in
                            ((reference,mog,vehicle,yolo) if opencv_first else (reference,mog,yolo)))+guard_ms}
                    final_result['summary']['provisional_occupied'] = final_result['provisional_occupied_count']
                    final_result['summary']['provisional_vacant'] = final_result['provisional_vacant_count']
                    for method,result in (('yolo',yolo),('final',final_result)):
                        runtime['reporters'][method].write(result,image)
                        runtime['windows'][method].update(when,window_snapshot(result,when,mapping))
                    joined.update(yolo=yolo,final=final_result)
                if supplemental and not opencv_first:
                    vehicle = vehicle_branch.analyze(image, reference)
                    by_slot = {s['slot_id']: s for s in vehicle['slots']}
                    final_slots = []
                    for row in joined['rows']:
                        evidence = by_slot[row['slot_id']]
                        evidence['bay_id'] = row['bay_id']
                        state, reason = final_decision(row['reference_state'], row['mog2_state'], evidence['state'])
                        row.update(vehicle_state=evidence['state'], vehicle_reason=evidence['reason'],
                                   vehicle_detector_score=evidence['detector_score'], vehicle_empty_difference=evidence['empty_difference'],
                                   vehicle_ms=vehicle['processing_duration_ms'], final_state=state, final_reason=reason,
                                   processed_at=vehicle['processed_at'])
                        final_slots.append({'slot_id': row['slot_id'], 'bay_id': row['bay_id'], 'state': state, 'reason': reason})
                    final_result = {**reference, 'method': 'combined_experimental_estimate', 'slots': final_slots,
                                    'summary': occupancy_summary(final_slots, available=any(s['state'] != 'unknown' for s in final_slots)),
                                    'processed_at': vehicle['processed_at'],
                                    'processing_duration_ms': sum((r.get('processing_duration_ms') or 0) for r in (reference,mog,vehicle))}
                    for method, result in (('vehicle',vehicle), ('final',final_result)):
                        runtime['reporters'][method].write(result, image)
                        runtime['windows'][method].update(when, window_snapshot(result,when,mapping))
                    joined.update(vehicle=vehicle, final=final_result)
                if alternate_policy:
                    from .alternate_policy import add_alternate
                    joined = add_alternate(joined)
                runtime["last"] = joined
                store.csv("observations.csv", joined["rows"])
                batch["recordings"].append(joined)
                runtime["samples"] += 1
            store.observation(batch)
            emit("comparison_samples", batch)
            ticks += 1
            next_sample = ticks * interval
            if frame_limit and ticks >= frame_limit:
                status = "frame_limit"
                break
        publish_windows([k for k,r in runtimes.items() if not r["ended"]], position, partial=True)
        status = "complete_with_errors" if status == "complete" and errors else status
        emit("done", f"{status.replace('_',' ').capitalize()} | {sum(r['samples'] for r in runtimes.values())} frames, "
                     f"{window_count} recording summaries | {out}")
        return 2 if errors else 0
    except KeyboardInterrupt:
        status = "stopped"
        publish_windows([k for k,r in runtimes.items() if not r["ended"]], position, partial=True)
        raise
    except Exception:
        status = "failed"
        raise
    finally:
        for runtime in runtimes.values():
            runtime["recording"].close()
        final = final_summary([r["last"] for r in runtimes.values() if r["last"] is not None], status)
        atomic_json(out / "final-summary.json", final)
        store.csv("final-summary.csv", final["rows"])
        if final["rows"]:
            emit("final_summary", final)
        atomic_json(out / "latest.json", {"run_active": False, "status": status,
            "current_occupancy_available": False, "historical_results": "history.jsonl and per-recording latest-window.json"})
        atomic_json(out / "run.json", {"status": status, "recording_ids": [c.id for c in clips], "sample_interval_seconds": interval,
            "decision_policy": OPENCV_FIRST_POLICY if opencv_first else GUARDED_DECISION_POLICY if verification else None,
            "summary_interval_seconds": 10, "sample_ticks": ticks, "skipped_ticks": skipped, "errors": errors,
            "samples_by_recording": {k:r["samples"] for k,r in runtimes.items()}, "window_count": window_count,
            "wall_clock_waits_enabled": not fast, "elapsed_seconds": time.monotonic()-begun,
            "comparison_scope": "separate_recording_periods", "independent_accuracy_measured": False})
