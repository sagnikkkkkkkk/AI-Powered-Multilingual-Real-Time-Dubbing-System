"""
Central configuration for the dubbing pipeline.

Change TTS_ENGINE to "xtts" once you've installed Coqui TTS and want real
few-shot voice cloning instead of the generic gTTS baseline voice.
See README.md -> "Upgrading to real voice cloning" for the exact steps.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
JOBS_DIR = BASE_DIR / "jobs_store"

for d in (UPLOAD_DIR, OUTPUT_DIR, JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# "baseline" -> gTTS (works everywhere, no cloning, good for demoing the pipeline)
# "edge"     -> Microsoft Edge neural TTS (free, no key, has real male/female
#               voices per language — recommended default)
# "xtts"     -> Coqui XTTS-v2 (real few-shot voice cloning, needs GPU + ~2GB model)
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge")

# Preserve background music/ambience by separating vocals before dubbing
# and layering the new speech back onto the original background track.
# Requires the `demucs` package; auto-falls-back to full-track-replace if
# it's not installed or separation fails for a given clip.
ENABLE_BACKGROUND_PRESERVATION = os.getenv("ENABLE_BACKGROUND_PRESERVATION", "true").lower() == "true"

# ASR model size: tiny/base/small/medium/large-v3 (bigger = more accurate, slower)
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")

# Flip on once Wav2Lip is set up (see app/pipeline/lipsync.py)
ENABLE_LIPSYNC = os.getenv("ENABLE_LIPSYNC", "false").lower() == "true"

SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "zh-CN": "Chinese (Simplified)",
    "ar": "Arabic",
}

# Edge neural TTS voice names per language and gender.
# Verify/update these against your Edge TTS version by running:
#   edge-tts --list-voices
# ...language support and exact voice names do occasionally change.
EDGE_VOICE_MAP = {
    "hi":    {"male": "hi-IN-MadhurNeural",    "female": "hi-IN-SwaraNeural"},
    "bn":    {"male": "bn-IN-BashkarNeural",   "female": "bn-IN-TanishaaNeural"},
    "ta":    {"male": "ta-IN-ValluvarNeural",  "female": "ta-IN-PallaviNeural"},
    "te":    {"male": "te-IN-MohanNeural",     "female": "te-IN-ShrutiNeural"},
    "mr":    {"male": "mr-IN-ManoharNeural",   "female": "mr-IN-AarohiNeural"},
    "gu":    {"male": "gu-IN-NiranjanNeural",  "female": "gu-IN-DhwaniNeural"},
    "kn":    {"male": "kn-IN-GaganNeural",     "female": "kn-IN-SapnaNeural"},
    "ml":    {"male": "ml-IN-MidhunNeural",    "female": "ml-IN-SobhanaNeural"},
    "es":    {"male": "es-ES-AlvaroNeural",    "female": "es-ES-ElviraNeural"},
    "fr":    {"male": "fr-FR-HenriNeural",     "female": "fr-FR-DeniseNeural"},
    "de":    {"male": "de-DE-ConradNeural",    "female": "de-DE-KatjaNeural"},
    "ja":    {"male": "ja-JP-KeitaNeural",     "female": "ja-JP-NanamiNeural"},
    "zh-CN": {"male": "zh-CN-YunxiNeural",     "female": "zh-CN-XiaoxiaoNeural"},
    "ar":    {"male": "ar-SA-HamedNeural",     "female": "ar-SA-ZariyahNeural"},
    # Punjabi isn't reliably available as a neural voice at time of writing —
    # tts.py falls back to gTTS automatically for any language missing here.
}
