import json
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.device import device_info, log_device_startup
from app.models_check import models_status
from app.jobs import JobStatus, create_job, get_job
from app.parse_timings import parse_timing_content
from app.experiment.routes import mount_experiment_page, router as experiment_router

app = FastAPI(title="Lyrics Aligner", version="0.1.0")
app.include_router(experiment_router)
mount_experiment_page(app)


@app.on_event("startup")
async def startup() -> None:
    if sys.platform == "win32":
        import asyncio

        loop = asyncio.get_running_loop()
        default = loop.get_exception_handler()

        def handler(loop_obj, context):
            msg = context.get("message", "")
            if "_ProactorBasePipeTransport" in msg or "_call_connection_lost" in msg:
                return
            if default:
                default(loop_obj, context)
            else:
                loop_obj.default_exception_handler(context)

        loop.set_exception_handler(handler)
    log_device_startup()


@app.get("/api/device")
async def get_device():
    info = device_info()
    info["demucs_models"] = models_status()
    return info

static_dir = settings.base_dir / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    page = static_dir / "index.html"
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/verify", response_class=HTMLResponse)
async def verify_page() -> HTMLResponse:
    page = static_dir / "verify.html"
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.post("/api/verify/parse")
async def verify_parse(timing: UploadFile = File(...)):
    suffix = Path(timing.filename or "t.txt").suffix
    raw = await timing.read()
    try:
        parsed = parse_timing_content(raw.decode("utf-8"), suffix)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    return {
        "lines": parsed,
        "count": len(parsed),
        "filename": timing.filename,
    }


@app.get("/api/sample")
async def sample_lyrics() -> dict:
    if not settings.sample_lyrics.exists():
        raise HTTPException(404, "Sample lyrics not found")
    return {
        "lyrics": settings.sample_lyrics.read_text(encoding="utf-8"),
        "audio_available": settings.sample_audio.exists(),
        "audio_name": settings.sample_audio.name if settings.sample_audio.exists() else None,
    }


@app.post("/api/align/sample")
async def align_sample(
    mode: str = Form("hq"),
    language: str = Form("ru"),
    skip_separation: bool = Form(False),
):
    if not settings.sample_audio.exists():
        raise HTTPException(404, "Sample audio not found")
    lyrics = settings.sample_lyrics.read_text(encoding="utf-8")
    audio_bytes = settings.sample_audio.read_bytes()
    job_id = create_job(
        audio_bytes=audio_bytes,
        audio_name=settings.sample_audio.name,
        lyrics=lyrics,
        mode=mode,
        language=language,
        skip_separation=skip_separation,
    )
    return {"job_id": job_id}


@app.post("/api/align")
async def align_upload(
    audio: UploadFile = File(...),
    lyrics: str = Form(...),
    mode: str = Form("hq"),
    language: str = Form("ru"),
    skip_separation: bool = Form(False),
):
    if not lyrics.strip():
        raise HTTPException(400, "Lyrics text is required")
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Audio file is empty")
    job_id = create_job(
        audio_bytes=data,
        audio_name=audio.filename or "upload.mp3",
        lyrics=lyrics,
        mode=mode,
        language=language,
        skip_separation=skip_separation,
    )
    return {"job_id": job_id}


@app.get("/api/align/{job_id}")
async def align_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/align/{job_id}/result.json")
async def align_result(job_id: str):
    path = settings.jobs_dir / job_id / "result.json"
    if not path.exists():
        job = get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") in (JobStatus.FAILED.value,):
            raise HTTPException(500, job.get("error") or "Job failed")
        raise HTTPException(409, "Result not ready")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".aac": "audio/aac",
}


def _find_job_audio(job_id: str) -> Path:
    job_dir = settings.jobs_dir / job_id
    if not job_dir.is_dir():
        raise HTTPException(404, "Job not found")
    for path in sorted(job_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
            return path
    raise HTTPException(404, "Audio not found for job")


def _file_or_404(job_id: str, name: str) -> FileResponse:
    path = settings.jobs_dir / job_id / name
    if not path.exists():
        raise HTTPException(404, f"{name} not found")
    return FileResponse(path, filename=name)


@app.get("/api/align/{job_id}/lyrics.lrc")
async def align_lrc(job_id: str):
    return _file_or_404(job_id, "lyrics.lrc")


@app.get("/api/align/{job_id}/lyrics.srt")
async def align_srt(job_id: str):
    return _file_or_404(job_id, "lyrics.srt")


@app.get("/api/align/{job_id}/quality.json")
async def align_quality(job_id: str):
    return _file_or_404(job_id, "quality.json")


@app.get("/api/align/{job_id}/audio")
async def align_audio(job_id: str):
    path = _find_job_audio(job_id)
    media = MEDIA_TYPES.get(path.suffix.lower(), "audio/mpeg")
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        headers={"Accept-Ranges": "bytes", "Cache-Control": "no-cache"},
    )
