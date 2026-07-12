from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.config import settings
from app.experiment.catalog import (
    bg_gif_path,
    bg_webm_path,
    find_audio,
    get_track,
    lines_json_path,
    list_tracks,
    track_name,
    words_json_path,
)
from app.experiment.yt_clip import ClipPrepareError, prepare_background

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/experiment", tags=["experiment"])

MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".aac": "audio/aac",
    ".gif": "image/gif",
    ".webm": "video/webm",
}


@router.get("/tracks")
async def experiment_tracks():
    return {"tracks": list_tracks()}


@router.get("/tracks/{track_id}")
async def experiment_track(track_id: str):
    name = track_name(track_id)
    track = get_track(name)
    if not track:
        raise HTTPException(404, "Track not found")
    return track


@router.get("/tracks/{track_id}/words.json")
async def experiment_words(track_id: str):
    path = words_json_path(track_name(track_id))
    if not path.exists():
        raise HTTPException(
            404,
            "words.json not found — запустите experiment_align.bat",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/tracks/{track_id}/lines.json")
async def experiment_lines(track_id: str):
    name = track_name(track_id)
    words_path = words_json_path(name)
    if words_path.exists():
        return json.loads(words_path.read_text(encoding="utf-8"))
    path = lines_json_path(name)
    if not path.exists():
        raise HTTPException(404, "timings not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/tracks/{track_id}/audio")
async def experiment_audio(track_id: str):
    name = track_name(track_id)
    path = find_audio(name)
    if not path:
        raise HTTPException(404, "Audio not found — положите .mp3 с тем же именем в Эксперимет/")
    media = MEDIA_TYPES.get(path.suffix.lower(), "audio/mpeg")
    return FileResponse(path, media_type=media, filename=path.name)


@router.get("/tracks/{track_id}/bg.gif")
async def experiment_bg_gif(track_id: str):
    path = bg_gif_path(track_name(track_id))
    if not path.exists():
        raise HTTPException(404, "Background GIF not ready — нажмите «Подготовить фон»")
    return FileResponse(path, media_type="image/gif", filename=path.name)


@router.get("/tracks/{track_id}/bg.webm")
async def experiment_bg_webm(track_id: str):
    path = bg_webm_path(track_name(track_id))
    if not path.exists():
        raise HTTPException(404, "Background webm not ready")
    return FileResponse(path, media_type="video/webm", filename=path.name)


@router.post("/tracks/{track_id}/prepare")
async def experiment_prepare(track_id: str):
    name = track_name(track_id)
    if not get_track(name):
        raise HTTPException(404, "Track not found")
    try:
        result = prepare_background(name)
    except ClipPrepareError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("prepare failed: %s", name)
        raise HTTPException(500, str(exc)) from exc
    return {"ok": True, "track": name, **result}


def mount_experiment_page(app) -> None:
    static_dir = settings.base_dir / "static"

    @app.get("/experiment", response_class=HTMLResponse)
    async def experiment_page() -> HTMLResponse:
        page = static_dir / "experiment.html"
        if not page.exists():
            raise HTTPException(404, "experiment.html not found")
        return HTMLResponse(page.read_text(encoding="utf-8"))
