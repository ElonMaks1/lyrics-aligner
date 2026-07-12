"""Проверка удаления Genius-предисловия."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pipeline.text_prep import parse_lyrics, strip_lyrics_preface

SAMPLES = [
    ROOT / "batch" / "рус" / "Радуга тяготения - Слава КПСС.txt",
    ROOT / "batch" / "англ + рус" / "ПСЖД - Слава КПСС.txt",
    ROOT / "batch" / "англ + рус" / "ОЙ ДА - Слава КПСС.txt",
    ROOT / "batch" / "англ + рус" / "WTBD - HAZE2FACE.txt",
    ROOT / "batch" / "рус" / "Мышь - Фазенда.txt",
]


def main() -> None:
    for path in SAMPLES:
        raw = path.read_text(encoding="utf-8")
        cleaned = strip_lyrics_preface(raw)
        lines, _ = parse_lyrics(raw)
        first = cleaned.splitlines()[0] if cleaned else ""
        print(f"=== {path.name} ===")
        print(f"  first line: {first[:80]}")
        print(f"  lyric lines: {len(lines)}")
        assert not first.startswith("31 Contributors"), path.name
        assert "[Текст песни" not in first, path.name
        assert lines, path.name
    print("OK")


if __name__ == "__main__":
    main()
