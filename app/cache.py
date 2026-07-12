from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from app.config import settings
from app.cache_meta import CACHE_VERSION


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_cache_key(audio_bytes: bytes, lyrics: str, config: dict[str, Any]) -> str:
    payload = json.dumps(
        {"lyrics": lyrics.strip(), "config": config, "cache_version": CACHE_VERSION},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return _hash_bytes(audio_bytes + b"|" + payload)


def cache_hit(key: str) -> Path | None:
    folder = settings.cache_dir / key
    result = folder / "result.json"
    if result.exists():
        return folder
    return None


def copy_cache_to_job(cache_folder: Path, job_dir: Path) -> None:
    for item in cache_folder.iterdir():
        dest = job_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def save_to_cache(key: str, job_dir: Path) -> None:
    folder = settings.cache_dir / key
    if folder.exists():
        shutil.rmtree(folder)
    shutil.copytree(job_dir, folder)
