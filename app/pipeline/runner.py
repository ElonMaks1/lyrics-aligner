from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

from app.config import settings
from app.device import device_info
from app.pipeline.align import align_known_lyrics
from app.pipeline.normalize import normalize_audio
from app.pipeline.postprocess import (
    assign_words_to_lines,
    compute_quality,
    fill_missing_words,
    interpolate_missing_lines,
    recover_low_coverage,
)
from app.pipeline.vocal_enhance import enhance_vocals_for_align
from app.models_check import resolve_demucs_model
from app.pipeline.separate import MODELS, separate_vocals
from app.pipeline.text_prep import is_mixed_language, parse_lyrics
from app.export.formats import export_all

logger = logging.getLogger(__name__)


def run_pipeline(
    audio_path: Path,
    lyrics_text: str,
    job_dir: Path,
    mode: str = "fast",
    language: str = "ru",
    skip_separation: bool = False,
    lines_only: bool = False,
    on_stage: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    def stage(name: str, status: str = "running") -> None:
        logger.info("stage %s: %s", name, status)
        if on_stage:
            on_stage(name, status)

    t0 = time.time()
    work = job_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    (job_dir / "lyrics_source.txt").write_text(lyrics_text, encoding="utf-8")

    stage("text_prep", "running")
    lyric_lines, align_text = parse_lyrics(lyrics_text)
    (job_dir / "lyrics_normalized.txt").write_text(align_text, encoding="utf-8")
    stage("text_prep", "done")

    stage("normalize", "running")
    normalized = normalize_audio(audio_path, work / "mono_16k.wav")
    stage("normalize", "done")

    align_input = normalized
    separation_used = False
    separation_warning: str | None = None
    model_fallback_note: str | None = None
    try:
        demucs_model_used, _ = resolve_demucs_model(MODELS.get(mode, "htdemucs"))
    except FileNotFoundError:
        demucs_model_used = None

    if not skip_separation:
        stage("separation", "running")
        try:
            def sep_progress(msg: str) -> None:
                stage("separation", msg)

            vocals, model_fallback_note = separate_vocals(
                audio_path, work, mode=mode, on_progress=sep_progress
            )
            norm_vocals = normalize_audio(vocals, work / "vocals_16k.wav")
            align_input = enhance_vocals_for_align(norm_vocals, work / "vocals_enhanced_16k.wav")
            separation_used = True
            stage("separation", "done")
            if model_fallback_note:
                separation_warning = model_fallback_note
        except Exception as exc:
            separation_warning = (
                "Demucs не отделил вокал — выравнивание по полному миксу. "
                "Бэк-вокал сильно портит тайминги. Перезапустите задачу или включите «Пропустить separation» "
                "только если вокал и так сухой."
            )
            logger.warning("separation failed, using full mix: %s", exc)
            stage("separation", "failed_fallback")
    else:
        separation_warning = "Separation пропущен — align по полному треку."
        stage("separation", "skipped")

    stage("align", "running")
    words = align_known_lyrics(align_input, align_text, language=language)
    stage("align", "done")

    stage("postprocess", "running")
    lines, low_conf = assign_words_to_lines(lyric_lines, words)
    lines = fill_missing_words(lines)
    lines = recover_low_coverage(lyric_lines, lines, words)
    lines = fill_missing_words(lines)
    lines = interpolate_missing_lines(lines)
    quality = compute_quality(lines, words, low_conf)
    stage("postprocess", "done")

    result = {
        "meta": {
            "mode": mode,
            "language": language,
            "mixed_language": is_mixed_language(language),
            "duration_sec": round(time.time() - t0, 2),
            "audio": str(audio_path.name),
            "device": device_info(),
            "separation_used": separation_used,
            "separation_warning": separation_warning,
            "demucs_model_requested": mode,
            "demucs_model_used": demucs_model_used,
        },
        "quality": quality,
        "lines": lines,
        "words_flat": words,
    }

    stage("export", "running")
    export_all(result, job_dir, lines_only=lines_only)
    (job_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    stage("export", "done")

    return result
