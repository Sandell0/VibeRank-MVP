"""Time-compress the grading wait in the raw demo recording and export mp4.

Usage: cut_demo_video.py <raw.webm> <t_click> <t_done> <out.mp4>
Keeps real time up to t_click+4s and from t_done-1s on; the middle
(the grading wait) is sped up so the video stays short.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe


def main() -> None:
    raw, t_click, t_done, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]

    probe = subprocess.run(
        [
            get_ffmpeg_exe(), "-i", raw, "-hide_banner",
        ],
        capture_output=True,
        text=True,
    )
    # Parse "Duration: 00:03:12.34" from stderr.
    duration = 0.0
    for line in probe.stderr.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            hours, minutes, seconds = stamp.split(":")
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            break
    if duration <= 0:
        raise RuntimeError("Could not read video duration")

    cut_a = min(t_click + 4.0, duration)
    cut_b = max(t_done - 1.0, cut_a + 1.0)
    wait = cut_b - cut_a
    speed = max(4.0, min(24.0, wait / 6.0))  # compressed wait lasts ~6s

    filters = (
        f"[0:v]trim=0:{cut_a:.2f},setpts=PTS-STARTPTS[v1];"
        f"[0:v]trim={cut_a:.2f}:{cut_b:.2f},setpts=(PTS-STARTPTS)/{speed:.2f}[v2];"
        f"[0:v]trim={cut_b:.2f}:{duration:.2f},setpts=PTS-STARTPTS[v3];"
        "[v1][v2][v3]concat=n=3:v=1[out]"
    )
    subprocess.run(
        [
            get_ffmpeg_exe(), "-y", "-i", raw,
            "-filter_complex", filters,
            "-map", "[out]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21",
            "-movflags", "+faststart",
            out,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    print(json.dumps({"out": out, "duration_s": duration, "wait_s": wait, "speed": speed}))


if __name__ == "__main__":
    main()
