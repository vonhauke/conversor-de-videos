"""Wrapper around the ffmpeg/ffprobe binaries: builds conversion commands
(including headerless .raw video, used for glitch-art workflows) and runs
them while reporting progress back to the GUI.
"""

import os
import re
import shutil
import subprocess
import sys

VIDEO_FORMATS = ["mp4", "mov", "avi", "mkv", "webm", "raw"]

# Bytes per pixel for common raw pixel formats. Needed to estimate the
# duration of a .raw file, since raw video has no header/metadata at all.
PIXEL_FORMAT_BYTES_PER_PIXEL = {
    "rgb24": 3,
    "bgr24": 3,
    "rgba": 4,
    "bgra": 4,
    "argb": 4,
    "abgr": 4,
    "gray": 1,
    "yuv420p": 1.5,
    "yuv422p": 2,
    "yuv444p": 3,
    "yuyv422": 2,
    "nv12": 1.5,
    "nv21": 1.5,
}

RAW_PIXEL_FORMATS = list(PIXEL_FORMAT_BYTES_PER_PIXEL.keys())

# Avoids a console window flashing up when we spawn ffmpeg from the GUI.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


def _bundled(name):
    """Caminho do binário embutido no .exe (PyInstaller), ou None se não houver."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return None
    candidate = os.path.join(base, "ffmpeg", f"{name}.exe")
    return candidate if os.path.isfile(candidate) else None


def find_ffmpeg():
    return _bundled("ffmpeg") or shutil.which("ffmpeg")


def find_ffprobe():
    return _bundled("ffprobe") or shutil.which("ffprobe")


def probe_duration_seconds(path):
    """Duration in seconds via ffprobe, or None if it can't be determined."""
    ffprobe = find_ffprobe()
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, text=True, timeout=15,
            creationflags=_NO_WINDOW,
        )
        return float(result.stdout.strip())
    except (ValueError, subprocess.SubprocessError):
        return None


def estimate_raw_duration_seconds(path, width, height, pix_fmt, fps):
    """Estimate a headerless .raw file's duration from its file size."""
    bytes_per_pixel = PIXEL_FORMAT_BYTES_PER_PIXEL.get(pix_fmt)
    if not bytes_per_pixel or width <= 0 or height <= 0 or fps <= 0:
        return None
    frame_size = width * height * bytes_per_pixel
    if frame_size <= 0:
        return None
    frame_count = os.path.getsize(path) / frame_size
    return frame_count / fps


def build_command(input_path, output_path, output_format, raw_in=None, raw_out=None):
    """Build the ffmpeg argument list for one conversion.

    raw_in: {"width", "height", "pix_fmt", "fps"} describing the input,
            required when input_path is a headerless .raw file.
    raw_out: {"pix_fmt"} describing the desired output, required when
             output_format == "raw".
    """
    cmd = [find_ffmpeg() or "ffmpeg", "-y"]

    if raw_in is not None:
        cmd += [
            "-f", "rawvideo",
            "-pixel_format", raw_in["pix_fmt"],
            "-video_size", f"{raw_in['width']}x{raw_in['height']}",
            "-framerate", str(raw_in["fps"]),
        ]

    cmd += ["-i", input_path]

    if output_format == "raw":
        cmd += ["-f", "rawvideo", "-pix_fmt", raw_out["pix_fmt"]]
    elif output_format in ("mp4", "mov"):
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]
    elif output_format == "mkv":
        cmd += ["-c:v", "libx264", "-c:a", "aac"]
    elif output_format == "avi":
        cmd += ["-c:v", "mpeg4", "-vtag", "xvid", "-c:a", "mp3"]
    elif output_format == "webm":
        cmd += ["-c:v", "libvpx-vp9", "-c:a", "libopus"]

    cmd += [output_path]
    return cmd


def run_conversion(cmd, on_progress=None, total_duration=None, should_cancel=None):
    """Run an ffmpeg command, calling on_progress(fraction) as it proceeds.

    fraction is a float in [0, 1] when total_duration is known, otherwise
    None (caller should show an indeterminate progress bar).
    should_cancel: optional callable polled between lines; if it returns
    True, the ffmpeg process is terminated and the conversion is aborted.
    Returns (success: bool, log: str, cancelled: bool).
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=_NO_WINDOW,
    )

    log_lines = []
    cancelled = False
    for line in process.stdout:
        log_lines.append(line)
        if should_cancel and should_cancel():
            cancelled = True
            process.terminate()
            break
        match = _TIME_RE.search(line)
        if match and on_progress:
            h, m, s = match.groups()
            elapsed = int(h) * 3600 + int(m) * 60 + float(s)
            on_progress(min(elapsed / total_duration, 1.0) if total_duration else None)

    process.wait()
    success = process.returncode == 0 and not cancelled
    if cancelled:
        log_lines.append("\n[Cancelado pelo usuário]\n")
    return success, "".join(log_lines), cancelled
