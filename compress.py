#!/usr/bin/env python3
"""Make PDF files smaller with Ghostscript."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PRESETS = {
    "high": {
        "pdfsettings": "/screen",
        "color": 72,
        "gray": 72,
        "mono": 150,
        "label": "Smaller file (screen or email)",
    },
    "medium": {
        "pdfsettings": "/ebook",
        "color": 150,
        "gray": 150,
        "mono": 300,
        "label": "Balanced",
    },
    "low": {
        "pdfsettings": "/printer",
        "color": 300,
        "gray": 300,
        "mono": 300,
        "label": "Better quality for print",
    },
}


def find_gs() -> str:
    for name in ("gs", "gswin64c"):
        path = shutil.which(name)
        if path:
            return path
    for candidate in (
        Path("/opt/homebrew/bin/gs"),
        Path("/usr/local/bin/gs"),
    ):
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        "Ghostscript is not installed. On a Mac, run: brew install ghostscript"
    )


def compress_pdf(src: Path, dest: Path, quality: str = "medium") -> dict:
    if quality not in PRESETS:
        raise ValueError(f"Unknown quality option: {quality}")
    if not src.is_file():
        raise FileNotFoundError(f"I cannot find this file: {src}")
    if src.suffix.lower() != ".pdf":
        raise ValueError("Please use a PDF file")

    preset = PRESETS[quality]
    dest.parent.mkdir(parents=True, exist_ok=True)
    gs = find_gs()

    cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={preset['pdfsettings']}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dSAFER",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dMonoImageDownsampleType=/Subsample",
        f"-dColorImageResolution={preset['color']}",
        f"-dGrayImageResolution={preset['gray']}",
        f"-dMonoImageResolution={preset['mono']}",
        f"-sOutputFile={dest}",
        str(src),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not dest.is_file():
        err = (result.stderr or result.stdout or "Ghostscript did not work").strip()
        raise RuntimeError(err)

    before = src.stat().st_size
    after = dest.stat().st_size
    # Ghostscript can make some files bigger. If that happens, keep the original.
    if after >= before:
        shutil.copy2(src, dest)
        after = dest.stat().st_size
        saved = 0
        note = "This PDF is already small. The file size did not go down."
    else:
        saved = round((1 - after / before) * 100, 1)
        note = None

    return {
        "before": before,
        "after": after,
        "saved_percent": saved,
        "quality": quality,
        "note": note,
    }


def _fmt(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Make PDF files smaller on your computer.")
    parser.add_argument("pdf", nargs="+", help="One or more PDF files")
    parser.add_argument(
        "-q",
        "--quality",
        choices=list(PRESETS),
        default="medium",
        help="high, medium, or low (default: medium)",
    )
    parser.add_argument("-o", "--output", help="Where to save the new file (one PDF only)")
    args = parser.parse_args()

    try:
        find_gs()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    paths = [Path(p).expanduser().resolve() for p in args.pdf]
    if args.output and len(paths) != 1:
        print("Use --output only when you pass one PDF file", file=sys.stderr)
        return 1

    for src in paths:
        dest = (
            Path(args.output).expanduser().resolve()
            if args.output
            else src.with_name(f"{src.stem}-compressed.pdf")
        )
        try:
            info = compress_pdf(src, dest, args.quality)
        except Exception as e:
            print(f"Error ({src.name}): {e}", file=sys.stderr)
            return 1
        print(
            f"{src.name}: {_fmt(info['before'])} -> {_fmt(info['after'])}"
            f" ({info['saved_percent']}% smaller) -> {dest}"
        )
        if info["note"]:
            print(f"  {info['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
