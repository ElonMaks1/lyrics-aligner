from __future__ import annotations

from pathlib import Path

CHECKPOINT_DIR = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"

# Demucs remote name -> файл в torch hub cache
CHECKPOINT_FILES = {
    "htdemucs": "955717e8-8726e21a.th",
    "htdemucs_ft": "f7e0c4bc-ba3fe64a.th",
}

MIN_BYTES = 1_000_000


def checkpoint_path(model_key: str) -> Path:
    name = CHECKPOINT_FILES.get(model_key)
    if not name:
        raise KeyError(model_key)
    return CHECKPOINT_DIR / name


def is_model_ready(model_key: str) -> bool:
    path = checkpoint_path(model_key)
    return path.is_file() and path.stat().st_size >= MIN_BYTES


def models_status() -> dict:
    out = {}
    for key, filename in CHECKPOINT_FILES.items():
        path = CHECKPOINT_DIR / filename
        ready = path.is_file() and path.stat().st_size >= MIN_BYTES
        out[key] = {
            "ready": ready,
            "file": str(path),
            "size_mb": round(path.stat().st_size / (1024 * 1024), 1) if ready else 0,
        }
    return out


def resolve_demucs_model(requested: str) -> tuple[str, str | None]:
    """Вернуть (имя модели для get_model, предупреждение или None)."""
    if is_model_ready(requested):
        return requested, None

    if requested == "htdemucs_ft" and is_model_ready("htdemucs"):
        return (
            "htdemucs",
            "Модель HQ (htdemucs_ft) не найдена — используется htdemucs. "
            f"Скачайте: {checkpoint_path('htdemucs_ft')}",
        )

    missing = checkpoint_path(requested)
    raise FileNotFoundError(
        f"Модель Demucs «{requested}» не установлена.\n"
        f"Ожидается файл: {missing}\n"
        "Запустите download_models.bat или скачайте .th вручную в эту папку."
    )
