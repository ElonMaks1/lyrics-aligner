"""
Эксперимент: Эксперимет/<имя>.mp3 + <имя>.txt -> <имя>.words.json
Таймкоды каждого слова для edit-визуала.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.export.formats import export_words_json
from app.pipeline.runner import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("experiment_align")

AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}


def find_pairs(folder: Path) -> list[tuple[Path, Path]]:
    texts = {
        p.stem.lower(): p
        for p in folder.iterdir()
        if p.suffix.lower() == ".txt" and not p.name.endswith("_YT.txt")
    }
    pairs: list[tuple[Path, Path]] = []
    for audio in folder.iterdir():
        if not audio.is_file() or audio.suffix.lower() not in AUDIO_EXT:
            continue
        txt = texts.get(audio.stem.lower())
        if txt:
            pairs.append((audio, txt))
        else:
            logger.warning("no .txt for %s", audio.name)
    return sorted(pairs, key=lambda x: x[0].name.lower())


def read_language(txt_path: Path) -> str:
    lang_path = txt_path.with_name(txt_path.stem + ".lang.txt")
    if lang_path.exists():
        return lang_path.read_text(encoding="utf-8").strip().lower() or "mixed"
    return "mixed"


def process_one(
    audio_path: Path,
    txt_path: Path,
    language: str | None,
    force: bool,
) -> dict:
    name = audio_path.stem
    out_path = settings.experiment_dir / f"{name}.words.json"
    if out_path.exists() and not force:
        logger.info("skip %s (words.json exists, use --force)", name)
        return {"name": name, "ok": True, "skipped": True}

    lang = language or read_language(txt_path)
    job_dir = settings.experiment_dir / "_work" / name
    job_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== %s (lang=%s) ===", name, lang)
    t0 = time.time()
    try:
        lyrics = txt_path.read_text(encoding="utf-8")
        result = run_pipeline(
            audio_path=audio_path,
            lyrics_text=lyrics,
            job_dir=job_dir,
            mode=settings.default_align_mode,
            language=lang,
            skip_separation=False,
            lines_only=False,
        )
        export_words_json(result, out_path, title=name)
        word_count = sum(len(ln.get("words") or []) for ln in result.get("lines", []))
        elapsed = time.time() - t0
        q = result.get("quality", {})
        row = {
            "name": name,
            "ok": True,
            "seconds": round(elapsed, 1),
            "lines": len(result.get("lines", [])),
            "words": word_count,
            "word_coverage": q.get("word_coverage"),
            "output": out_path.name,
        }
        logger.info("OK %s — %d words (%.0fs)", name, word_count, elapsed)
        return row
    except Exception as exc:
        logger.exception("FAIL %s: %s", name, exc)
        return {"name": name, "ok": False, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Word-level align for experiment visual")
    parser.add_argument("name", nargs="?", help="Track name (default: all pairs in Эксперимет/)")
    parser.add_argument("--lang", default=None, help="ru | en | mixed (default: mixed or *.lang.txt)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing .words.json")
    args = parser.parse_args()

    folder = settings.experiment_dir
    pairs = find_pairs(folder)
    if args.name:
        pairs = [(a, t) for a, t in pairs if a.stem == args.name]
        if not pairs:
            logger.error("Not found: %s (.mp3 + .txt)", args.name)
            sys.exit(1)

    if not pairs:
        logger.error("No mp3+txt pairs in %s", folder)
        sys.exit(1)

    reports = [process_one(a, t, args.lang, args.force) for a, t in pairs]
    report_path = folder / "experiment_align_report.json"
    report_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in reports if r.get("ok") and not r.get("skipped"))
    logger.info("Done: %d processed. Report: %s", ok, report_path)


if __name__ == "__main__":
    main()
