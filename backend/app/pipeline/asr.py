"""
Stage 1: Automatic Speech Recognition + timing/emotion cues.

Uses faster-whisper (CTranslate2-based Whisper) which is CPU-friendly and
gives per-segment timestamps — needed later for duration-aware translation
and re-muxing the dubbed audio back onto the video.
"""
from dataclasses import dataclass
from typing import List
from ..config import WHISPER_MODEL_SIZE

_model = None


@dataclass
class Segment:
    start: float
    end: float
    text: str
    # crude prosody proxy: words-per-second tells us if the line was
    # delivered fast (excited/urgent) or slow (somber/deliberate)
    pace: float


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        # int8 for CPU speed; switch to "float16" + device="cuda" if you have a GPU
        _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def transcribe(audio_path: str) -> List[Segment]:
    model = _get_model()
    segments, _info = model.transcribe(audio_path, vad_filter=True)

    results = []
    for seg in segments:
        n_words = max(len(seg.text.split()), 1)
        duration = max(seg.end - seg.start, 0.01)
        results.append(
            Segment(
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                pace=n_words / duration,
            )
        )
    return results
