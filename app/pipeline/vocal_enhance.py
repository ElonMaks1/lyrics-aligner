import logging
from pathlib import Path

import librosa
import numpy as np
import scipy.signal as signal
import soundfile as sf

logger = logging.getLogger(__name__)


def enhance_vocals_for_align(input_path: Path, output_path: Path, sr: int = 16000) -> Path:
    """Подчистить stem для aligner: HPF, preemphasis, нормализация громкости."""
    audio, _ = librosa.load(str(input_path), sr=sr, mono=True)
    audio = librosa.effects.preemphasis(audio, coef=0.97)
    sos = signal.butter(2, 80, btype="highpass", fs=sr, output="sos")
    audio = signal.sosfilt(sos, audio).astype(np.float32)
    peak = float(np.max(np.abs(audio)) or 1.0)
    audio = audio / peak * 0.92
    rms = float(np.sqrt(np.mean(audio**2)) or 1e-8)
    target_rms = 0.12
    audio = np.clip(audio * (target_rms / rms), -1.0, 1.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), audio, sr)
    logger.info("vocal_enhance: %s", output_path.name)
    return output_path
