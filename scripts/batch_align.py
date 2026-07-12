"""
Пакетная обработка: batch/англ, batch/рус, batch/англ + рус
-> batch_output/lines/<имя>.lines.json (все треки в одной папке)
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import BATCH_FOLDERS, settings
from app.export.formats import export_lines_json
from app.pipeline.runner import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("batch")

AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


def find_pairs(folder: Path) -> list[tuple[Path, Path]]:
    texts = {p.stem.lower(): p for p in folder.iterdir() if p.suffix.lower() == ".txt"}
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


def _safe_stem(name: str) -> str:
    cleaned = _INVALID_CHARS.sub("_", name).strip(" .")
    return cleaned or "track"


def unique_lines_name(folder_name: str, track_name: str, used: set[str]) -> str:
    """Имя файла без .lines.json; при коллизии добавляется префикс папки."""
    base = _safe_stem(track_name)
    if base not in used:
        used.add(base)
        return base
    prefixed = _safe_stem(f"{folder_name} - {track_name}")
    if prefixed not in used:
        used.add(prefixed)
        return prefixed
    n = 2
    while True:
        candidate = _safe_stem(f"{folder_name} - {track_name} ({n})")
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1


def process_folder(
    folder_name: str,
    language: str,
    lines_dir: Path,
    used_names: set[str],
) -> list[dict]:
    in_dir = settings.batch_in_dir / folder_name
    pairs = find_pairs(in_dir)
    logger.info("=== %s (%s): %d tracks ===", folder_name, language, len(pairs))
    report: list[dict] = []

    for audio_path, txt_path in pairs:
        name = audio_path.stem
        out_name = unique_lines_name(folder_name, name, used_names)
        logger.info("--- %s / %s -> %s.lines.json ---", folder_name, name, out_name)
        t0 = time.time()
        job_dir = settings.batch_out_dir / "_work" / folder_name / name
        job_dir.mkdir(parents=True, exist_ok=True)

        try:
            lyrics = txt_path.read_text(encoding="utf-8")
            result = run_pipeline(
                audio_path=audio_path,
                lyrics_text=lyrics,
                job_dir=job_dir,
                mode=settings.default_align_mode,
                language=language,
                skip_separation=False,
                lines_only=True,
            )
            out_path = export_lines_json(result, lines_dir, out_name)
            elapsed = time.time() - t0
            q = result.get("quality", {})
            row = {
                "folder": folder_name,
                "track": name,
                "output": out_path.name,
                "ok": True,
                "seconds": round(elapsed, 1),
                "line_coverage": q.get("line_coverage"),
                "lines": len([l for l in result.get("lines", []) if l.get("start") is not None]),
            }
            logger.info("OK %s -> %s (%.0fs, lines=%s)", name, out_path.name, elapsed, row["lines"])
        except Exception as exc:
            row = {
                "folder": folder_name,
                "track": name,
                "ok": False,
                "error": str(exc),
            }
            logger.exception("FAIL %s: %s", name, exc)

        report.append(row)

    return report


def main() -> None:
    lines_dir = settings.batch_lines_dir
    lines_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()

    all_reports: list[dict] = []
    for folder_name, language in BATCH_FOLDERS.items():
        all_reports.extend(process_folder(folder_name, language, lines_dir, used_names))

    summary_path = settings.batch_out_dir / "batch_report.json"
    summary_path.write_text(
        json.dumps(all_reports, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ok = sum(1 for r in all_reports if r.get("ok"))
    logger.info(
        "Done: %d/%d OK. JSON: %s. Report: %s",
        ok,
        len(all_reports),
        lines_dir,
        summary_path,
    )


if __name__ == "__main__":
    main()
