from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import settings
from app.experiment.catalog import asset_dir_name, bg_gif_path, bg_webm_path, read_youtube_url

logger = logging.getLogger(__name__)


class ClipPrepareError(RuntimeError):
    pass


def _ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise ClipPrepareError(
            "ffmpeg не найден. Установите ffmpeg в PATH или: pip install imageio-ffmpeg"
        ) from exc


def _ffprobe_duration(ffmpeg: str, video_path: Path) -> float:
    proc = subprocess.run(
        [ffmpeg, "-i", str(video_path)],
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not match:
        raise ClipPrepareError("Не удалось определить длительность видео")
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def _download_video(url: str, out_dir: Path) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:
        raise ClipPrepareError("Установите yt-dlp: pip install yt-dlp") from exc

    out_template = str(out_dir / "source.%(ext)s")
    opts = {
        "format": "bestvideo[height<=720][ext=mp4]/best[height<=720][ext=mp4]/best[height<=720]",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise ClipPrepareError("yt-dlp не вернул информацию о видео")

    candidates = sorted(out_dir.glob("source.*"))
    if not candidates:
        raise ClipPrepareError("Видео не скачалось")
    return candidates[0]


def prepare_background(
    base_name: str,
    clip_seconds: float = 30.0,
    gif_width: int = 426,
    gif_fps: int = 10,
) -> dict:
    url = read_youtube_url(base_name)
    if not url:
        raise ClipPrepareError(f"Нет ссылки YouTube: {base_name}_YT.txt")

    asset_dir = settings.experiment_assets_dir / asset_dir_name(base_name)
    asset_dir.mkdir(parents=True, exist_ok=True)
    gif_out = bg_gif_path(base_name)
    webm_out = bg_webm_path(base_name)
    gif_out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = _ffmpeg_exe()

    with tempfile.TemporaryDirectory(prefix="yt_clip_") as tmp:
        tmp_dir = Path(tmp)
        logger.info("download: %s", url)
        video_path = _download_video(url, tmp_dir)
        duration = _ffprobe_duration(ffmpeg, video_path)
        clip = min(clip_seconds, max(duration - 1.0, 1.0))
        start = max(0.0, (duration - clip) / 2.0)
        logger.info("clip: start=%.1fs len=%.1fs (video %.1fs)", start, clip, duration)

        clip_mp4 = tmp_dir / "clip.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(video_path),
                "-t",
                f"{clip:.3f}",
                "-an",
                "-vf",
                f"scale={gif_width}:-2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                str(clip_mp4),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        palette = tmp_dir / "palette.png"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(clip_mp4),
                "-vf",
                f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos,palettegen=stats_mode=diff",
                str(palette),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(clip_mp4),
                "-i",
                str(palette),
                "-lavfi",
                f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
                "-loop",
                "0",
                str(gif_out),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(clip_mp4),
                "-c:v",
                "libvpx-vp9",
                "-b:v",
                "0",
                "-crf",
                "35",
                "-an",
                "-loop",
                "0",
                str(webm_out),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if not webm_out.exists():
            webm_out = None

    return {
        "gif": str(gif_out),
        "webm": str(webm_out) if webm_out and webm_out.exists() else None,
        "gif_bytes": gif_out.stat().st_size if gif_out.exists() else 0,
        "webm_bytes": webm_out.stat().st_size if webm_out and webm_out.exists() else 0,
        "clip_start_sec": round(start, 2),
        "clip_len_sec": round(clip, 2),
        "source_duration_sec": round(duration, 2),
    }
