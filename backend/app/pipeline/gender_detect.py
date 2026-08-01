"""
Detects whether the source speaker sounds male or female by analyzing the
fundamental frequency (pitch) of their voice — the actual acoustic signal,
not guesswork. This is what was silently missing before: nothing was
inspecting the audio at all, so the pipeline always fell through to
whatever the TTS engine's single default voice happened to be.

Typical average speaking F0 ranges (widely used biomedical/speech-science
reference values):
  - Adult male voices:   ~85-180 Hz
  - Adult female voices: ~165-255 Hz
There's a gray zone around 155-180 Hz — for those, other cues (formant
spacing) would help, but pitch alone is a solid, cheap first pass.
"""
from dataclasses import dataclass


@dataclass
class GenderResult:
    gender: str        # "male" or "female"
    confidence: str     # "high" | "low" — low if the pitch fell in the gray zone
    mean_f0_hz: float


def detect_gender(audio_path: str) -> GenderResult:
    import librosa
    import numpy as np

    y, sr = librosa.load(audio_path, sr=16000, mono=True)

    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),   # ~65 Hz
        fmax=librosa.note_to_hz("C6"),   # ~1047 Hz
        sr=sr,
    )
    voiced_f0 = f0[voiced_flag] if voiced_flag is not None else f0[~np.isnan(f0)]
    voiced_f0 = voiced_f0[~np.isnan(voiced_f0)]

    if len(voiced_f0) == 0:
        # No reliably voiced frames (e.g. very short/noisy clip) — default
        # to female since that's the more common TTS baseline, but flag it
        # as low confidence so the UI can show that it's a guess.
        return GenderResult(gender="female", confidence="low", mean_f0_hz=0.0)

    mean_f0 = float(np.median(voiced_f0))

    if mean_f0 < 155:
        gender = "male"
    elif mean_f0 > 180:
        gender = "female"
    else:
        # Gray zone — pick the closer boundary but mark it uncertain
        gender = "male" if mean_f0 < 167.5 else "female"

    confidence = "low" if 155 <= mean_f0 <= 180 else "high"
    return GenderResult(gender=gender, confidence=confidence, mean_f0_hz=mean_f0)
