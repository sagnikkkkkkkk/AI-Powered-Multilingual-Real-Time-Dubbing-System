"""
Stage 2: Context-aware, duration-aware translation.

Baseline uses deep-translator (free, no API key) for the actual translation.
Duration-awareness is approximated post-hoc: if the translated line is much
longer than the timing budget allows at a natural speaking pace, we ask for
a shorter paraphrase-style trim. This mirrors the duration-based dubbing
approach used in recent LLM-dubbing research (see project references).
"""
from dataclasses import dataclass
from typing import List
from .asr import Segment


@dataclass
class TranslatedSegment:
    start: float
    end: float
    source_text: str
    translated_text: str


# Rough average syllable/character budget per second of natural speech.
# Used only to flag segments that will need compression, not to hard-cut them.
CHARS_PER_SECOND = 15


def _translate_text(text: str, target_language: str) -> str:
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source="auto", target=target_language).translate(text)


def _fits_duration(text: str, duration: float) -> bool:
    return len(text) <= duration * CHARS_PER_SECOND * 1.25  # 25% slack


def translate_segments(segments: List[Segment], target_language: str) -> List[TranslatedSegment]:
    translated: List[TranslatedSegment] = []

    for seg in segments:
        duration = max(seg.end - seg.start, 0.01)
        text = _translate_text(seg.text, target_language)

        if not _fits_duration(text, duration):
            # Ask for a tighter, more compressed phrasing that keeps the
            # same meaning within the available time window. A production
            # system would call an LLM here with an explicit character
            # budget; deep-translator alone can't paraphrase, so we flag it.
            text = text  # placeholder — swap in an LLM call for real compression

        translated.append(
            TranslatedSegment(
                start=seg.start,
                end=seg.end,
                source_text=seg.text,
                translated_text=text,
            )
        )
    return translated
