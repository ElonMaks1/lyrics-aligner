from __future__ import annotations

import json
from pathlib import Path

from app.pipeline.separate import MODELS
from app.models_check import is_model_ready, resolve_demucs_model

# Увеличьте при смене пайплайна, чтобы не отдавать старые результаты
CACHE_VERSION = "3"


def refresh_cached_result_meta(job_dir: Path, mode: str) -> None:
    """Обновить meta в закэшированном result.json (модели могли появиться позже)."""
    result_path = job_dir / "result.json"
    if not result_path.exists():
        return

    data = json.loads(result_path.read_text(encoding="utf-8"))
    meta = data.get("meta") or {}
    requested = MODELS.get(mode, "htdemucs")

    try:
        actual, warn = resolve_demucs_model(requested)
    except FileNotFoundError as exc:
        meta["demucs_model_used"] = None
        meta["separation_warning"] = str(exc)
        data["meta"] = meta
        result_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    meta["demucs_model_used"] = actual
    meta["demucs_model_requested"] = requested

    old_warn = meta.get("separation_warning") or ""
    if warn:
        meta["separation_warning"] = warn
    elif "htdemucs_ft" in old_warn and "не найдена" in old_warn and is_model_ready("htdemucs_ft"):
        meta["separation_warning"] = None

    data["meta"] = meta
    result_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
