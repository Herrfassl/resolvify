import shutil
import subprocess
from pathlib import Path

from resolvify import core


def test_collect_and_output_path(tmp_path):
    (tmp_path / "a.MP4").touch()
    (tmp_path / "b.txt").touch()
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.mp4").touch()  # not recursive
    assert core.collect_videos([tmp_path]) == [tmp_path / "a.MP4"]
    assert core.output_path(tmp_path / "a.MP4") == tmp_path / "resolve" / "a.mov"
    assert core.output_path(tmp_path / "a.MP4", "/x") == Path("/x/a.mov")


def test_convert_real_file(tmp_path):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    src = tmp_path / "in.mp4"
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=d=1:s=320x240:r=25",
         "-f", "lavfi", "-i", "sine=d=1", "-c:v", "mpeg4", "-c:a", "aac", str(src)],
        check=True,
    )
    dst = core.output_path(src)
    seen = []
    ok, msg = core.convert(ffmpeg, ffprobe, src, dst, on_progress=seen.append)
    assert ok, msg
    assert dst.exists() and not list(dst.parent.glob("*.part.mov"))
    assert seen and seen[-1] == 1.0
    codecs = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(dst)],
        capture_output=True, text=True,
    ).stdout.split()
    assert codecs == ["dnxhd", "pcm_s16le"]


def test_convert_error_reported(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_text("not a video")
    ok, msg = core.convert(shutil.which("ffmpeg"), shutil.which("ffprobe"), bad, core.output_path(bad))
    assert not ok and msg
