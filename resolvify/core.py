import os
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mts", ".m2ts", ".wmv", ".flv"}
OUT_DIRNAME = "resolve"
_WIN = sys.platform == "win32"


def find_tool(name):
    """Bundled binary next to the app (Windows release), else the one on PATH."""
    exe = name + (".exe" if _WIN else "")
    base = Path(getattr(sys, "_MEIPASS", Path(sys.argv[0]).resolve().parent))
    bundled = base / exe
    return str(bundled) if bundled.is_file() else shutil.which(name)


def collect_videos(paths):
    """Files as given, folders expanded one level (not recursive). Sorted, deduplicated."""
    found = {}
    for p in map(Path, paths):
        items = p.iterdir() if p.is_dir() else [p]
        for f in items:
            if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
                found[f.resolve()] = f
    return sorted(found.values())


def output_path(src, out_dir=None):
    src = Path(src)
    return (Path(out_dir) if out_dir else src.parent / OUT_DIRNAME) / (src.stem + ".mov")


def build_cmd(ffmpeg, src, dst):
    # cfr: phone videos are often variable framerate, which breaks sync in Resolve.
    # map: first video + all audio, drops the data streams phones add.
    return [
        ffmpeg, "-y", "-i", str(src),
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "dnxhd", "-profile:v", "dnxhr_hq", "-pix_fmt", "yuv422p",
        "-c:a", "pcm_s16le", "-fps_mode", "cfr",
        "-progress", "pipe:1", "-nostats", str(dst),
    ]


def duration(ffprobe, src):
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(src)],
        capture_output=True, text=True, creationflags=_flags(),
    ).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def _flags():
    return subprocess.CREATE_NO_WINDOW if _WIN else 0


def convert(ffmpeg, ffprobe, src, dst, on_progress=lambda f: None, cancelled=lambda: False):
    """Convert src to dst. Returns (ok, message). Writes to a .part file, renames on success."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.stem + ".part.mov")
    total = duration(ffprobe, src)
    proc = subprocess.Popen(
        build_cmd(ffmpeg, src, part),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        errors="replace", creationflags=_flags(),
    )
    tail = []
    for line in proc.stdout:
        if cancelled():
            proc.terminate()
            proc.wait()
            part.unlink(missing_ok=True)
            return False, "cancelled"
        key, _, val = line.strip().partition("=")
        if key == "out_time_us" and total and val.lstrip("-").isdigit():
            on_progress(min(max(int(val) / 1e6 / total, 0.0), 1.0))
        elif "=" not in line:
            tail = (tail + [line.strip()])[-5:]
    if proc.wait() != 0:
        part.unlink(missing_ok=True)
        return False, " | ".join(tail) or f"ffmpeg exit code {proc.returncode}"
    os.replace(part, dst)
    on_progress(1.0)
    return True, "ok"
