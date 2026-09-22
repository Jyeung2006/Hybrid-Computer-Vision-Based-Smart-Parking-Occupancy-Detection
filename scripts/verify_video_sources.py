"""Inspect the downloaded media with a separately permitted FFmpeg executable.

This verifies media transport/decoding, not OpenCV or parking inference. It
does not modify Windows policy or try to load the blocked OpenCV library.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from parking_probe.catalog import CLIPS, PROJECT_ROOT, checksum


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", required=True, type=Path)
    args = parser.parse_args()
    executable = str(args.ffmpeg.resolve())

    def inspect(clip):
        path = PROJECT_ROOT / "data" / "chad" / clip.member
        digest, crc = checksum(path)
        info = subprocess.run([executable, "-hide_banner", "-i", str(path)],
                              capture_output=True, text=True, timeout=15)
        duration = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", info.stderr)
        match = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b.*? ([\d.]+) fps", info.stderr)
        decode = subprocess.run([executable, "-hide_banner", "-loglevel", "error", "-i", str(path),
                                 "-map", "0:v:0", "-an", "-progress", "pipe:1", "-f", "null", "-"],
                                capture_output=True, text=True, timeout=60)
        frames = re.findall(r"^frame=(\d+)", decode.stdout, flags=re.MULTILINE)
        return {"id": clip.id, "member": clip.member, "bytes": path.stat().st_size,
                "sha256": digest, "size_crc_sha256_match": path.stat().st_size == clip.size and digest == clip.sha256 and crc == clip.crc32,
                "resolution": [int(match[1]), int(match[2])] if match else None,
                "fps_displayed_by_ffmpeg": float(match[3]) if match else None,
                "container_duration_seconds": int(duration[1])*3600+int(duration[2])*60+float(duration[3]) if duration else None,
                "full_decode_exit_code": decode.returncode, "decoded_frames": int(frames[-1]) if frames else None,
                "decoder_errors": decode.stderr[:1000], "opencv_inference_tested": False}

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(inspect, CLIPS))
    output = PROJECT_ROOT / "runs" / "verification" / "chad-media-inspection.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"verification": "FFmpeg media inspection only", "clips": records}, indent=2) + "\n")
    print(output)
    print(json.dumps(records, indent=2))
    return int(any(not r["size_crc_sha256_match"] or r["full_decode_exit_code"] != 0 or not r["decoded_frames"] for r in records))


if __name__ == "__main__":
    raise SystemExit(main())
