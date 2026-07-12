from __future__ import annotations

import logging
import os

import torch

logger = logging.getLogger(__name__)


def resolve_device(prefer: str | None = None) -> str:
    """Return 'cuda' or 'cpu'. prefer: auto | cuda | cpu (env LYRICS_DEVICE)."""
    prefer = (prefer or os.getenv("LYRICS_DEVICE", "auto")).lower().strip()
    cuda_ok = torch.cuda.is_available()

    if prefer == "cpu":
        return "cpu"
    if prefer == "cuda":
        if not cuda_ok:
            logger.warning("CUDA requested but unavailable — falling back to CPU")
            return "cpu"
        return "cuda"
    return "cuda" if cuda_ok else "cpu"


def device_info() -> dict:
    dev = resolve_device()
    info = {
        "device": dev,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        props = torch.cuda.get_device_properties(0)
        info["vram_gb"] = round(props.total_memory / (1024**3), 2)
    return info


def log_device_startup() -> None:
    info = device_info()
    if info["device"] == "cuda":
        logger.info(
            "GPU: %s (%.1f GB VRAM), torch %s",
            info.get("gpu"),
            info.get("vram_gb", 0),
            info["torch"],
        )
    else:
        logger.warning(
            "Running on CPU — install CUDA PyTorch for GPU: "
            "pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124"
        )
