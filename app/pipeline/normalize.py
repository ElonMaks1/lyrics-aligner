import logging
from pathlib import Path

import librosa
import soundfile as sf

logger = logging.getLogger(__name__)


def normalize_audio(input_path: Path, output_path: Path, sample_rate: int = 16000) -> Path:
    logger.info("normalize: %s -> mono %d Hz", input_path.name, sample_rate)
    audio, _ = librosa.load(str(input_path), sr=sample_rate, mono=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), audio, sample_rate)
    return output_path
