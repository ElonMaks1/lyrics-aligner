from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote, unquote

from app.config import settings

AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def track_id(name: str) -> str:
    return quote(name, safe="")


def track_name(track_id_value: str) -> str:
    return unquote(track_id_value)


def read_youtube_url(base_name: str) -> str | None:
    yt_path = settings.experiment_dir / f"{base_name}_YT.txt"
    if not yt_path.exists():
        return None
    text = yt_path.read_text(encoding="utf-8")
    match = URL_RE.search(text)
    return match.group(0) if match else None


def find_audio(base_name: str) -> Path | None:
    folder = settings.experiment_dir
    for ext in AUDIO_EXT:
        path = folder / f"{base_name}{ext}"
        if path.is_file():
            return path
    return None


def asset_dir_name(base_name: str) -> str:
    name = base_name.strip()
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    return name or "track"


def bg_gif_path(base_name: str) -> Path:
    return settings.experiment_assets_dir / asset_dir_name(base_name) / "bg.gif"


def bg_webm_path(base_name: str) -> Path:
    return settings.experiment_assets_dir / asset_dir_name(base_name) / "bg.webm"


def words_json_path(base_name: str) -> Path:
    return settings.experiment_dir / f"{base_name}.words.json"


def lines_json_path(base_name: str) -> Path:
    return settings.experiment_dir / f"{base_name}.lines.json"


def _count_words(payload: dict) -> int:
    total = 0
    for line in payload.get("lines", []):
        total += len(line.get("words") or [])
    return total


def _discover_bases(folder: Path) -> set[str]:
    bases: set[str] = set()
    for path in folder.glob("*.words.json"):
        bases.add(path.name[: -len(".words.json")])
    for path in folder.glob("*.lines.json"):
        bases.add(path.name[: -len(".lines.json")])
    for txt in folder.glob("*.txt"):
        if txt.name.endswith("_YT.txt") or txt.name.endswith(".lang.txt"):
            continue
        if find_audio(txt.stem):
            bases.add(txt.stem)
    return bases


def list_tracks() -> list[dict]:
    folder = settings.experiment_dir
    tracks: list[dict] = []

    for base in sorted(_discover_bases(folder), key=str.lower):
        words_path = words_json_path(base)
        lines_path = lines_json_path(base)
        has_words = words_path.exists()
        has_lines = lines_path.exists()

        line_count = 0
        word_count = 0
        title = base

        if has_words:
            try:
                payload = json.loads(words_path.read_text(encoding="utf-8"))
                line_count = len(payload.get("lines", []))
                word_count = _count_words(payload)
                title = payload.get("title", base)
            except json.JSONDecodeError:
                pass
        elif has_lines:
            try:
                payload = json.loads(lines_path.read_text(encoding="utf-8"))
                line_count = len(payload.get("lines", []))
                title = payload.get("title", base)
            except json.JSONDecodeError:
                pass

        audio = find_audio(base)
        gif = bg_gif_path(base)
        webm = bg_webm_path(base)
        tracks.append(
            {
                "id": track_id(base),
                "name": base,
                "title": title,
                "lines": line_count,
                "words": word_count,
                "has_words": has_words,
                "has_lines": has_lines,
                "needs_align": audio is not None and not has_words,
                "youtube_url": read_youtube_url(base),
                "has_audio": audio is not None,
                "audio_name": audio.name if audio else None,
                "has_background": gif.exists() or webm.exists(),
                "background_gif": gif.exists(),
                "background_webm": webm.exists(),
            }
        )

    return tracks


def get_track(base_name: str) -> dict | None:
    for track in list_tracks():
        if track["name"] == base_name:
            return track
    return None
