from __future__ import annotations

import logging
from typing import Any

import torch

logger = logging.getLogger(__name__)

_demucs: dict[str, Any] = {}
_mms: dict[tuple[str, str], tuple[Any, Any]] = {}


def get_demucs_model(model_name: str):
    from demucs.pretrained import get_model

    if model_name in _demucs:
        logger.info("demucs: reuse in-memory %s", model_name)
        return _demucs[model_name]

    logger.info("demucs: load checkpoint from disk -> %s (once per server run)", model_name)
    model = get_model(model_name)
    if hasattr(model, "models"):
        logger.info("demucs: bag of %d sub-models (each = full progress bar)", len(model.models))
    model.cpu()
    model.eval()
    _demucs[model_name] = model
    return model


def get_mms_model(device: str, dtype: torch.dtype):
    from ctc_forced_aligner import load_alignment_model

    key = (device, str(dtype))
    if key in _mms:
        logger.info("mms: reuse in-memory on %s", device)
        return _mms[key]

    logger.info("mms: load weights into %s (once per server run)", device)
    _mms[key] = load_alignment_model(device, dtype=dtype)
    return _mms[key]


def clear_model_cache() -> None:
    _demucs.clear()
    _mms.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
