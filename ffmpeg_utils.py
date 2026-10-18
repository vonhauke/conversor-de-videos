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
    """Caminho do binário embutido no executável (PyInstaller), ou None se não houver."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return None
    ext = ".exe" if sys.platform == "win32" else ""
    candidate = os.path.join(base, "ffmpeg", f"{name}{ext}")
    return candidate if os.path.isfile(candidate) else None


def find_ffmpeg():
    return _bundled("ffmpeg") or shutil.which("ffmpeg")


def find_ffprobe():
    return _bundled("ffprobe") or shutil.which("ffprobe")


# Codificadores H.264 acelerados por hardware (placa de vídeo ou chip de vídeo do processador),
# em ordem de preferência, com a qualidade ajustada para ficar próxima do x264.
HW_H264 = {
    "h264_nvenc": ["-preset", "p4", "-rc", "vbr", "-cq", "25", "-b:v", "0", "-pix_fmt", "yuv420p"],
    "h264_qsv": ["-preset", "veryfast", "-global_quality", "25", "-pix_fmt", "nv12"],
    "h264_amf": ["-quality", "speed", "-rc", "cqp", "-qp_i", "25", "-qp_p", "25", "-pix_fmt", "yuv420p"],
}
# Fallback em software: "veryfast" é bem mais rápido que o padrão ("medium") com arquivo quase do mesmo tamanho.
CPU_H264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
# VP9 no modo padrão é MUITO lento (vários segundos de processamento por segundo de vídeo).
VP9_FAST = ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1",
            "-tile-columns", "2", "-b:v", "0", "-crf", "33"]

_hw_cache = {}


def detect_hw_h264():
    """Nome do primeiro codificador H.264 de hardware que funciona neste PC, ou None.
    Testa de verdade com um mini vídeo (estar listado no ffmpeg não garante que a máquina tenha o hardware)."""
    if "enc" in _hw_cache:
        return _hw_cache["enc"]
    found = None
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        for name, args in HW_H264.items():
            try:
                result = subprocess.run(
                    [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=0.2",
                     "-c:v", name, *args, "-f", "null", "-"],
                    capture_output=True, timeout=20, creationflags=_NO_WINDOW,
                )
            except (subprocess.SubprocessError, OSError):
                continue
            if result.returncode == 0:
                found = name
                break
    _hw_cache["enc"] = found
    return found


def uses_hardware(cmd):
    return any(arg in HW_H264 for arg in cmd)


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


# Codecs que cada contêiner aceita sem recodificar (-c copy). Lista conservadora: só o que
# toca bem em qualquer programa. O que não está aqui é recodificado.
COPY_VIDEO = {
    "mp4": {"h264", "hevc"},
    "mov": {"h264", "hevc"},
    "mkv": {"h264", "hevc", "vp9", "av1", "mpeg4", "mjpeg"},
    "webm": {"vp8", "vp9", "av1"},
    "avi": {"mpeg4"},
}
COPY_AUDIO = {
    "mp4": {"aac", "mp3"},
    "mov": {"aac", "mp3"},
    "mkv": {"aac", "mp3", "opus", "vorbis", "flac", "ac3"},
    "webm": {"opus", "vorbis"},
    "avi": {"mp3", "ac3", "pcm_s16le"},
}
AUDIO_ENCODER = {"mp4": "aac", "mov": "aac", "mkv": "aac", "avi": "mp3", "webm": "libopus"}
# AVI: MPEG-4 (xvid), que gera arquivos pequenos.
AVI_MPEG4 = ["-c:v", "mpeg4", "-vtag", "xvid"]


def probe_codecs(path):
    """(codec de vídeo, codec de áudio) do arquivo via ffprobe; None onde não houver ou não der para ler."""
    ffprobe = find_ffprobe()
    if not ffprobe:
        return None, None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,codec_name",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW,
        )
    except subprocess.SubprocessError:
        return None, None
    video = audio = None
    for line in result.stdout.splitlines():
        nome, _, tipo = line.strip().partition(",")
        if tipo == "video" and video is None:
            video = nome
        elif tipo == "audio" and audio is None:
            audio = nome
    return video, audio


def uses_copy(cmd):
    """True se o comando copia o vídeo sem recodificar."""
    return any(a == "copy" and cmd[i - 1] == "-c:v" for i, a in enumerate(cmd) if i)


def build_command(input_path, output_path, output_format, raw_in=None, raw_out=None,
                  use_hw=True, allow_copy=True):
    """Build the ffmpeg argument list for one conversion.

    raw_in: {"width", "height", "pix_fmt", "fps"} describing the input,
            required when input_path is a headerless .raw file.
    raw_out: {"pix_fmt"} describing the desired output, required when
             output_format == "raw".
    use_hw: tenta o codificador H.264 de hardware (mp4/mov/mkv) quando houver um.
    allow_copy: copia vídeo/áudio sem recodificar quando o codec já serve no formato de destino
                (segundos em vez de minutos, sem perda de qualidade).
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
    else:
        vcodec = acodec = None
        if allow_copy and raw_in is None:
            vcodec, acodec = probe_codecs(input_path)
        copy_video = vcodec in COPY_VIDEO[output_format]
        copy_audio = acodec in COPY_AUDIO[output_format]

        # só o 1º vídeo e o(s) áudio(s): evita falhas com faixas de dados (ex.: timecode de iPhone)
        cmd += ["-map", "0:v:0", "-map", "0:a?"]

        if copy_video:
            cmd += ["-c:v", "copy"]
            if vcodec == "hevc" and output_format in ("mp4", "mov"):
                cmd += ["-tag:v", "hvc1"]  # necessário para o HEVC tocar no iPhone/Mac/QuickTime
        elif output_format in ("mp4", "mov", "mkv"):
            hw = detect_hw_h264() if use_hw else None
            cmd += ["-c:v", hw, *HW_H264[hw]] if hw else CPU_H264
        elif output_format == "avi":
            cmd += AVI_MPEG4
        elif output_format == "webm":
            cmd += VP9_FAST

        cmd += ["-c:a", "copy" if copy_audio else AUDIO_ENCODER[output_format]]

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
