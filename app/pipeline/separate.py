from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from pathlib import Path

import torch

from app.config import settings
from app.device import resolve_device
from app.model_cache import get_demucs_model
from app.models_check import resolve_demucs_model

logger = logging.getLogger(__name__)

MODELS = {
    "fast": "htdemucs",
    "balanced": "htdemucs",
    "hq": "htdemucs_ft",
}

# HQ = bag из 4 sub-models; shifts>1 умножает время (каждый sub-model × shifts проходов)
SHIFTS = {"fast": 1, "balanced": 1, "hq": 1}


def _model_segment_sec(model) -> float:
    if hasattr(model, "segment") and model.segment:
        return float(model.segment)
    if hasattr(model, "max_allowed_segment"):
        return float(model.max_allowed_segment)
    return 10.0


def _run_apply(model, wav, device: str, shifts: int, segment: float | None, split: bool):
    from demucs.apply import apply_model

    mix = wav[None].contiguous().float()
    return apply_model(
        model,
        mix,
        device=device,
        shifts=shifts,
        split=split,
        overlap=0.25,
        progress=True,
        segment=segment,
    )[0]


def separate_vocals(
    input_path: Path,
    work_dir: Path,
    mode: str = "fast",
    on_progress: Callable[[str], None] | None = None,
) -> tuple[Path, str | None]:
    from demucs.audio import save_audio
    from demucs.separate import load_track

    requested = MODELS.get(mode, "htdemucs")
    model_name, model_warn = resolve_demucs_model(requested)
    device = resolve_device(settings.device)
    shifts = SHIFTS.get(mode, 1)

    logger.info("separation: model=%s (requested %s) device=%s", model_name, requested, device)
    if model_warn:
        logger.warning("separation: %s", model_warn)
    if on_progress:
        on_progress(f"loading {model_name}")

    t0 = time.time()
    try:
        model = get_demucs_model(model_name)
    except Exception as exc:
        raise RuntimeError(
            "Не удалось загрузить модель Demucs. Проверьте файл в "
            "%USERPROFILE%\\.cache\\torch\\hub\\checkpoints\\"
        ) from exc

    segment_sec = _model_segment_sec(model)
    n_sub = len(model.models) if hasattr(model, "models") else 1
    est_note = f"~{n_sub * shifts} проход(ов) по треку" if n_sub > 1 else "1 проход"
    logger.info(
        "separation: segment=%.1fs, %s (не скачивание — inference на GPU)",
        segment_sec,
        est_note,
    )

    out_root = work_dir / "demucs_out" / model_name
    out_root.mkdir(parents=True, exist_ok=True)

    wav = load_track(input_path, model.audio_channels, model.samplerate)
    ref = wav.mean(0)
    wav = ((wav - ref.mean()) / ref.std()).contiguous().float()

    attempts: list[tuple[str, str, float | None, bool]] = [
        (device, "cuda+split", segment_sec, True),
        (device, "cuda+full", segment_sec, False),
        ("cpu", "cpu+split", segment_sec, True),
    ]
    seen: set[tuple] = set()
    sources = None
    last_err: Exception | None = None

    for dev, label, seg, split in attempts:
        key = (dev, seg, split)
        if key in seen:
            continue
        seen.add(key)
        if on_progress:
            on_progress(label)
        logger.info("separation: try %s segment=%s split=%s", label, seg, split)
        try:
            with torch.inference_mode():
                sources = _run_apply(model, wav, dev, shifts, seg, split)
            logger.info("separation: ok with %s", label)
            break
        except Exception as exc:
            last_err = exc
            logger.warning("separation: %s failed: %s", label, exc)
            if dev == "cuda":
                torch.cuda.empty_cache()

    if sources is None:
        raise RuntimeError(f"Demucs separation failed: {last_err}") from last_err

    sources = sources * ref.std() + ref.mean()

    stem = "vocals"
    if stem not in model.sources:
        raise ValueError(f"model {model_name} has no vocals stem: {model.sources}")

    idx = model.sources.index(stem)
    vocals_path = out_root / input_path.stem / f"{stem}.wav"
    vocals_path.parent.mkdir(parents=True, exist_ok=True)
    save_audio(sources[idx], str(vocals_path), samplerate=model.samplerate)

    dest = work_dir / "vocals.wav"
    shutil.copy2(vocals_path, dest)
    elapsed = time.time() - t0
    logger.info("separation: done in %.1fs -> %s", elapsed, dest)
    if on_progress:
        on_progress(f"done in {elapsed:.0f}s")
    return dest, model_warn
