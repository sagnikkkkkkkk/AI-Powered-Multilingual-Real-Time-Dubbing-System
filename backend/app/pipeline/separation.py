"""
Separates the source audio into a vocals track and a background (music/
ambience) track using Demucs. This is what was missing before: the old
pipeline replaced the *entire* audio track with synthesized speech, which
silently deleted any background music along with the original dialogue.

With this module:
  - ASR and voice-reference extraction run on the isolated vocals track
    (cleaner transcription, cleaner voice sample for gender detection).
  - The dubbed speech is layered back on top of the original background
    track, so music/ambience survives untouched.

Demucs is a heavy dependency (~2GB with torch, downloads a model on first
use) and slow on CPU. If it isn't installed or separation fails for any
reason, the pipeline logs it and falls back to the old full-track-replace
behavior rather than crashing the whole job.
"""
from pathlib import Path
from typing import Optional, Tuple


def is_available() -> bool:
    try:
        import demucs.separate  # noqa: F401
        return True
    except ImportError:
        return False


def separate_vocals(audio_path: str, work_dir: Path) -> Optional[Tuple[str, str]]:
    """
    Returns (vocals_path, background_path) as wav files, or None if
    separation isn't available / fails — callers should handle the
    fallback case explicitly rather than assuming this always succeeds.
    """
    if not is_available():
        return None

    try:
        import demucs.separate

        sep_out = work_dir / "separated"
        sep_out.mkdir(exist_ok=True)

        # "htdemucs" is Demucs' default pretrained model; --two-stems
        # collapses drums/bass/other into a single "no_vocals" track,
        # which is exactly the "background" track we want here.
        demucs.separate.main([
            "--two-stems", "vocals",
            "-o", str(sep_out),
            "-n", "htdemucs",
            str(audio_path),
        ])

        stem_name = Path(audio_path).stem
        result_dir = sep_out / "htdemucs" / stem_name
        vocals = result_dir / "vocals.wav"
        background = result_dir / "no_vocals.wav"

        if vocals.exists() and background.exists():
            return str(vocals), str(background)
        return None

    except Exception as exc:
        # Any failure here (missing model download, OOM, unsupported
        # input, etc.) should degrade gracefully, not take the job down —
        # but print the real reason so it's diagnosable instead of a
        # silent, unexplained "background music removed" result.
        print(f"[separation] vocal/background separation failed: {exc!r}")
        return None
