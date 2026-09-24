# resolvify

Small GUI that converts videos to **DNxHR HQ** (`.mov`, PCM audio) so they load with a preview in
DaVinci Resolve Free on Linux, which cannot decode H.264/H.265/AAC.

- Drop video files or folders (folders are not scanned recursively) into the window, press Start.
- Output goes to a `resolve/` folder next to each original, or a folder you choose. Existing outputs are skipped, originals are never touched.
- Variable framerate is always converted to constant framerate (avoids sync problems in Resolve).
- Expect large files, roughly 10x the size of the source.

## Run from source

Needs Python 3.10+, `ffmpeg` and `ffprobe` on PATH.

    pip install -r requirements.txt
    python -m resolvify

## Releases

Pushing a tag like `v0.1.0` builds a Windows zip (ffmpeg bundled) and a Linux binary (needs system ffmpeg)
via GitHub Actions and attaches them to the release.

## Tests

    python -m pytest
