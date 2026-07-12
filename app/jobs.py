from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from app.cache import cache_hit, copy_cache_to_job, make_cache_key, save_to_cache
from app.cache_meta import refresh_cached_result_meta
from app.config import settings
from app.pipeline.runner import run_pipeline

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CACHED = "cached"


_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_dir(job_id: str) -> Path:
    return settings.jobs_dir / job_id


def _write_status(job_id: str, payload: dict[str, Any]) -> None:
    with _lock:
        _jobs[job_id] = payload
    path = _job_dir(job_id) / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        if job_id in _jobs:
            return _jobs[job_id]
    path = _job_dir(job_id) / "status.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def create_job(
    audio_bytes: bytes,
    audio_name: str,
    lyrics: str,
    mode: str,
    language: str,
    skip_separation: bool = False,
) -> str:
    job_id = str(uuid.uuid4())
    job_dir = _job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    audio_path = job_dir / audio_name
    audio_path.write_bytes(audio_bytes)

    config = {
        "mode": mode,
        "language": language,
        "skip_separation": skip_separation,
    }
    cache_key = make_cache_key(audio_bytes, lyrics, config)

    cached = cache_hit(cache_key)
    if cached:
        copy_cache_to_job(cached, job_dir)
        refresh_cached_result_meta(job_dir, mode)
        _write_status(
            job_id,
            {
                "id": job_id,
                "status": JobStatus.CACHED.value,
                "cache_key": cache_key,
                "created_at": _now(),
                "finished_at": _now(),
                "stages": {"cache": "hit"},
                "error": None,
            },
        )
        return job_id

    _write_status(
        job_id,
        {
            "id": job_id,
            "status": JobStatus.QUEUED.value,
            "cache_key": cache_key,
            "created_at": _now(),
            "finished_at": None,
            "stages": {},
            "error": None,
        },
    )

    thread = threading.Thread(
        target=_run_worker,
        args=(job_id, audio_path, lyrics, mode, language, skip_separation, cache_key),
        daemon=True,
    )
    thread.start()
    return job_id


def _run_worker(
    job_id: str,
    audio_path: Path,
    lyrics: str,
    mode: str,
    language: str,
    skip_separation: bool,
    cache_key: str,
) -> None:
    stages: dict[str, str] = {}

    def on_stage(name: str, status: str) -> None:
        stages[name] = status
        _write_status(
            job_id,
            {
                **(get_job(job_id) or {}),
                "status": JobStatus.RUNNING.value,
                "stages": dict(stages),
            },
        )

    try:
        _write_status(
            job_id,
            {
                **(get_job(job_id) or {}),
                "status": JobStatus.RUNNING.value,
                "started_at": _now(),
                "stages": stages,
            },
        )
        run_pipeline(
            audio_path=audio_path,
            lyrics_text=lyrics,
            job_dir=_job_dir(job_id),
            mode=mode,
            language=language,
            skip_separation=skip_separation,
            on_stage=on_stage,
        )
        save_to_cache(cache_key, _job_dir(job_id))
        _write_status(
            job_id,
            {
                **(get_job(job_id) or {}),
                "status": JobStatus.DONE.value,
                "finished_at": _now(),
                "stages": stages,
                "error": None,
            },
        )
    except Exception as exc:
        logger.exception("job %s failed", job_id)
        _write_status(
            job_id,
            {
                **(get_job(job_id) or {}),
                "status": JobStatus.FAILED.value,
                "finished_at": _now(),
                "stages": stages,
                "error": str(exc),
            },
        )
