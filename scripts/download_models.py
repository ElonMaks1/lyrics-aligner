"""Скачать веса Demucs вручную (если torch hub зависает на 0%)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"

MODELS = {
    "htdemucs": (
        "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th",
        "955717e8-8726e21a.th",
        80_200_000,
    ),
    "htdemucs_ft": (
        "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/f7e0c4bc-ba3fe64a.th",
        "f7e0c4bc-ba3fe64a.th",
        80_200_000,
    ),
}


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for p in dest.parent.glob(dest.name + ".*.partial"):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            print(f"  (skip locked partial {p.name} — stop other python jobs first)")

    print(f"Downloading {url}")
    print(f"  -> {dest}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err = None
    for attempt in range(1, 6):
        try:
            done = 0
            if tmp.exists():
                done = tmp.stat().st_size
            headers = {}
            if done:
                headers["Range"] = f"bytes={done}-"
            with requests.get(url, stream=True, timeout=(30, 300), headers=headers) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0)) + done
                mode = "ab" if done else "wb"
                with open(tmp, mode) as f:
                    for chunk in r.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            pct = 100 * done / total
                            print(
                                f"\r  {pct:5.1f}% ({done // 1024 // 1024} / {total // 1024 // 1024} MB)",
                                end="",
                            )
            print()
            tmp.replace(dest)
            last_err = None
            break
        except requests.RequestException as exc:
            last_err = exc
            print(f"\n  attempt {attempt}/5 failed: {exc}")
    if last_err:
        raise last_err
    print(f"  OK ({dest.stat().st_size // 1024 // 1024} MB)")


def main() -> None:
    names = sys.argv[1:] or ["htdemucs"]
    for name in names:
        if name not in MODELS:
            print(f"Unknown model: {name}. Choose: {', '.join(MODELS)}")
            sys.exit(1)
        url, filename, _ = MODELS[name]
        dest = CHECKPOINT_DIR / filename
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f"Skip {name}: already at {dest}")
            continue
        download(url, dest)
    print("\nФайлы должны лежать в:", CHECKPOINT_DIR)
    print("htdemucs    -> 955717e8-8726e21a.th  (Fast/Balanced)")
    print("htdemucs_ft -> f7e0c4bc-ba3fe64a.th  (режим HQ)")
    print("\nDone. Restart start.bat and run alignment again.")


if __name__ == "__main__":
    main()
