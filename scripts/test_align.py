"""CLI smoke test on bundled sample track."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.pipeline.runner import run_pipeline


def main() -> None:
    skip_sep = "--skip-separation" in sys.argv
    mode = "fast"
    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]

    lyrics = settings.sample_lyrics.read_text(encoding="utf-8")
    job_dir = settings.jobs_dir / "smoke_test"
    if job_dir.exists():
        import shutil

        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True)

    print(f"audio={settings.sample_audio}")
    print(f"mode={mode} skip_separation={skip_sep}")

    result = run_pipeline(
        audio_path=settings.sample_audio,
        lyrics_text=lyrics,
        job_dir=job_dir,
        mode=mode,
        language="ru",
        skip_separation=skip_sep,
        on_stage=lambda n, s: print(f"  [{n}] {s}"),
    )

    q = result["quality"]
    print("\n=== quality ===")
    for k, v in q.items():
        print(f"  {k}: {v}")
    print(f"\nresult: {job_dir / 'result.json'}")
    print(f"lrc:    {job_dir / 'lyrics.lrc'}")


if __name__ == "__main__":
    main()
