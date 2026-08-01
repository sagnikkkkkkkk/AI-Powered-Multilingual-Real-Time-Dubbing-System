"""
Stage 3 + 4: Voice-selected TTS and duration fitting.

Three engines behind one interface, selected by config.TTS_ENGINE:

- "edge":     Microsoft Edge neural TTS. Free, no API key, and — unlike
              gTTS — has genuinely distinct male/female voices per
              language (config.EDGE_VOICE_MAP). This is why voice gender
              selection wasn't working before: gTTS only ever exposes one
              generic voice per language, so there was nothing to select
              between. Default engine now.
- "baseline": gTTS. Automatic fallback if edge-tts can't reach its
              endpoint (offline/firewalled), or if a language+gender
              combination isn't in EDGE_VOICE_MAP.
- "xtts":     Coqui XTTS-v2 — real few-shot voice cloning from the actor's
              own reference clip. Needs GPU + ~2GB model, opt-in.

All engines synthesize a raw clip; video_utils.fit_duration() is then
applied by the orchestrator to time-fit it to its slot (that step is what
fixes segment overlap — it doesn't happen inside this module).
"""
from pathlib import Path
from ..config import TTS_ENGINE, EDGE_VOICE_MAP


def synthesize_baseline(text: str, lang: str, out_path: Path, **_ignored) -> Path:
    from gtts import gTTS
    # gTTS uses base language codes (e.g. "zh-CN" -> "zh-CN" is fine, but
    # some locale suffixes aren't accepted) — strip region if it errors.
    try:
        gTTS(text=text, lang=lang).save(str(out_path))
    except ValueError:
        gTTS(text=text, lang=lang.split("-")[0]).save(str(out_path))
    return out_path


def synthesize_edge(text: str, lang: str, out_path: Path, gender: str = "female", **_ignored) -> Path:
    import asyncio
    import edge_tts

    voice_options = EDGE_VOICE_MAP.get(lang)
    if not voice_options or gender not in voice_options:
        # No mapped voice for this language/gender — fall back rather than fail.
        return synthesize_baseline(text, lang, out_path)

    voice = voice_options[gender]

    async def _run():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(out_path))

    try:
        asyncio.run(_run())
    except Exception:
        # Network issue, rate limit, etc. — fall back so the job doesn't die.
        return synthesize_baseline(text, lang, out_path)

    return out_path


def synthesize_xtts(text: str, lang: str, out_path: Path, reference_audio: str, pace: float = 1.0, **_ignored) -> Path:
    """
    Real voice-cloning path. Requires: pip install TTS
    and a short (6-10s) clean clip of the actor's voice as `reference_audio`.
    """
    from TTS.api import TTS  # noqa: heavy import, only loaded if this path is used

    model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    model.tts_to_file(
        text=text,
        speaker_wav=reference_audio,
        language=lang,
        file_path=str(out_path),
        speed=pace,
    )
    return out_path


def synthesize(
    text: str,
    lang: str,
    out_path: Path,
    reference_audio: str | None = None,
    pace: float = 1.0,
    gender: str = "female",
) -> Path:
    if TTS_ENGINE == "xtts":
        if not reference_audio:
            raise ValueError("xtts engine requires reference_audio (a clip of the actor's voice)")
        return synthesize_xtts(text, lang, out_path, reference_audio, pace)
    if TTS_ENGINE == "edge":
        return synthesize_edge(text, lang, out_path, gender=gender)
    return synthesize_baseline(text, lang, out_path)
