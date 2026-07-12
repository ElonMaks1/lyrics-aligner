import logging
from pathlib import Path

import torch

from app.config import settings
from app.device import resolve_device
from app.model_cache import get_mms_model
from app.pipeline.mixed_text import preprocess_text_mixed
from app.pipeline.text_prep import is_mixed_language, language_to_iso3, primary_iso3_for_mixed

logger = logging.getLogger(__name__)


def align_known_lyrics(
    audio_path: Path,
    text: str,
    language: str = "ru",
    batch_size: int = 16,
) -> list[dict]:
    from ctc_forced_aligner import (
        generate_emissions,
        get_alignments,
        get_spans,
        load_audio,
        postprocess_results,
        preprocess_text,
    )

    device = resolve_device(settings.device)
    dtype = torch.float16 if device == "cuda" else torch.float32
    mixed = is_mixed_language(language)
    iso3 = language_to_iso3(language)
    logger.info("align: device=%s lang=%s mixed=%s", device, language, mixed)

    model, tokenizer = get_mms_model(device, dtype)
    waveform = load_audio(str(audio_path), model.dtype, model.device)
    emissions, stride = generate_emissions(model, waveform, batch_size=batch_size)

    if mixed:
        tokens_starred, text_starred = preprocess_text_mixed(
            text,
            primary_iso3=primary_iso3_for_mixed(language),
            star_frequency="segment",
        )
    else:
        tokens_starred, text_starred = preprocess_text(
            text,
            romanize=True,
            language=iso3,
        )

    segments, scores, blank_token = get_alignments(emissions, tokens_starred, tokenizer)
    spans = get_spans(tokens_starred, segments, blank_token)
    word_timestamps = postprocess_results(text_starred, spans, stride, scores)

    words: list[dict] = []
    for item in word_timestamps:
        if isinstance(item, dict):
            words.append(
                {
                    "text": str(item.get("text", item.get("word", ""))),
                    "start": float(item["start"]),
                    "end": float(item["end"]),
                    "score": float(item.get("score", 0.0)),
                }
            )
        elif hasattr(item, "text"):
            words.append(
                {
                    "text": str(item.text),
                    "start": float(item.start),
                    "end": float(item.end),
                    "score": float(getattr(item, "score", 0.0)),
                }
            )
        else:
            words.append(
                {
                    "text": str(item[0]),
                    "start": float(item[1]),
                    "end": float(item[2]),
                    "score": float(item[3]) if len(item) > 3 else 0.0,
                }
            )

    logger.info("align: %d words", len(words))
    return words
