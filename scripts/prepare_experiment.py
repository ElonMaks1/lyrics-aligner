"""
Скачать клип с YouTube (из *_YT.txt), вырезать 30с из середины, сохранить bg.gif.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.experiment.catalog import list_tracks
from app.experiment.yt_clip import ClipPrepareError, prepare_background

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prepare_experiment")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare experiment background clips")
    parser.add_argument("name", nargs="?", help="Track base name (default: all)")
    args = parser.parse_args()

    tracks = list_tracks()
    if args.name:
        tracks = [t for t in tracks if t["name"] == args.name]
        if not tracks:
            logger.error("Track not found: %s", args.name)
            sys.exit(1)

    if not tracks:
        logger.error("No *.lines.json in Эксперимет/")
        sys.exit(1)

    for track in tracks:
        logger.info("=== %s ===", track["name"])
        if track.get("has_background"):
            logger.info("skip: background already exists")
            continue
        if not track.get("youtube_url"):
            logger.warning("skip: no _YT.txt url")
            continue
        try:
            info = prepare_background(track["name"])
            logger.info(
                "OK gif=%s bytes webm=%s bytes",
                info.get("gif_bytes"),
                info.get("webm_bytes"),
            )
        except ClipPrepareError as exc:
            logger.error("FAIL: %s", exc)


if __name__ == "__main__":
    main()
