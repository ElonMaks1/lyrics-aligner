from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    cache_dir: Path = data_dir / "cache"
    jobs_dir: Path = data_dir / "jobs"
    sample_audio: Path = base_dir / "Фазенда - Мужики.mp3"
    sample_lyrics: Path = base_dir / "Фазенда - Мужики.txt"
    batch_in_dir: Path = base_dir / "batch"
    batch_out_dir: Path = base_dir / "batch_output"
    batch_lines_dir: Path = batch_out_dir / "lines"
    experiment_dir: Path = base_dir / "Эксперимет"
    experiment_assets_dir: Path = experiment_dir / "_assets"
    default_align_mode: str = "hq"
    host: str = "127.0.0.1"
    port: int = 8765
    min_word_confidence: float = 0.35
    min_word_log_score: float = -20.0
    line_gap_threshold_sec: float = 1.8
    line_padding_ms: int = 80
    target_coverage: float = 0.90
    # auto | cuda | cpu — для RTX 3050 оставьте auto или cuda
    device: str = "auto"

    class Config:
        env_prefix = "LYRICS_"


settings = Settings()
BATCH_FOLDERS = {
    "англ": "en",
    "рус": "ru",
    "англ + рус": "mixed",
}

for d in (settings.data_dir, settings.cache_dir, settings.jobs_dir, settings.batch_in_dir, settings.batch_out_dir, settings.batch_lines_dir, settings.experiment_dir, settings.experiment_assets_dir):
    d.mkdir(parents=True, exist_ok=True)
for name in BATCH_FOLDERS:
    (settings.batch_in_dir / name).mkdir(parents=True, exist_ok=True)
