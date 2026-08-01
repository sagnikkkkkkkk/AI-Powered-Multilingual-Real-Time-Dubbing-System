"""
Stage 6 (optional/stretch goal): Lip-sync realignment.

Not run by default — real lip-sync models (Wav2Lip, VideoReTalking) need a
GPU and a separate install from their GitHub repos, not pip. This module
gives you the exact integration point: call run_lipsync() after muxing the
dubbed audio, before returning the final video, once you've set it up.

Setup (Wav2Lip):
  1. git clone https://github.com/Rudrabha/Wav2Lip
  2. Download their pretrained checkpoint (see repo README)
  3. Point WAV2LIP_DIR below at the cloned repo
  4. Flip config.ENABLE_LIPSYNC = True
"""
import subprocess
from pathlib import Path

WAV2LIP_DIR = Path("./Wav2Lip")  # set this to your cloned Wav2Lip path
WAV2LIP_CHECKPOINT = WAV2LIP_DIR / "checkpoints" / "wav2lip_gan.pth"


def run_lipsync(video_path: str, audio_path: str, out_path: str) -> str:
    if not WAV2LIP_CHECKPOINT.exists():
        raise FileNotFoundError(
            "Wav2Lip checkpoint not found. This stage is optional — see "
            "lipsync.py docstring for setup steps, or leave it disabled."
        )
    subprocess.run(
        [
            "python", str(WAV2LIP_DIR / "inference.py"),
            "--checkpoint_path", str(WAV2LIP_CHECKPOINT),
            "--face", video_path,
            "--audio", audio_path,
            "--outfile", out_path,
        ],
        check=True,
    )
    return out_path
