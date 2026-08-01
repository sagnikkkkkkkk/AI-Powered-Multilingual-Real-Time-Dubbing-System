"""
Stage 5: Stitching per-segment dubbed audio back onto the original video,
respecting each segment's original start time.
"""
from pathlib import Path
from typing import List
from pydub import AudioSegment


def get_duration(wav_path: str) -> float:
    audio = AudioSegment.from_file(wav_path)
    return len(audio) / 1000.0


def fit_duration(wav_path: str, target_seconds: float, out_path: str, min_speed: float = 0.75, max_speed: float = 1.9) -> str:
    """
    Time-stretches a synthesized clip to fit inside `target_seconds` using
    ffmpeg's atempo filter, which changes speed WITHOUT changing pitch —
    critical here since a pitch-shifted clip would undo the male/female
    voice selection. This is the actual fix for segments overlapping: a
    segment is now only ever as long as the time slot it was assigned,
    instead of running past it into the next line.

    If the clip is already shorter than the slot, it's left untouched
    (a shorter dubbed line is fine — a longer one overlapping the next
    line is not).
    """
    current = get_duration(wav_path)
    if current <= target_seconds or current <= 0:
        AudioSegment.from_file(wav_path).export(out_path, format="wav")
        return out_path

    speed = current / target_seconds
    speed = max(min_speed, min(speed, max_speed))  # keep it intelligible

    # atempo only accepts 0.5-2.0 per filter instance; chain if needed
    # (not required within our clamped range, but written defensively).
    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")

    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-filter:a", ",".join(filters), out_path],
        check=True,
        capture_output=True,
    )
    return out_path


def mix_background(vocals_path: str, background_path: str, out_path: str, background_gain_db: float = -2.0) -> str:
    """Layers dubbed vocals on top of the original background/music track."""
    vocals = AudioSegment.from_file(vocals_path)
    background = AudioSegment.from_file(background_path) + background_gain_db

    if len(background) < len(vocals):
        background = background + AudioSegment.silent(duration=len(vocals) - len(background))

    mixed = background.overlay(vocals)
    mixed.export(out_path, format="wav")
    return out_path


def extract_audio(video_path: str, out_wav_path: str) -> str:
    from moviepy.editor import VideoFileClip
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(out_wav_path, fps=16000, verbose=False, logger=None)
    clip.close()
    return out_wav_path


def extract_reference_clip(audio_path: str, out_path: str, start: float = 0.0, duration: float = 8.0) -> str:
    """Grab a short clean clip of the actor's voice to use as the cloning reference."""
    audio = AudioSegment.from_file(audio_path)
    clip = audio[int(start * 1000): int((start + duration) * 1000)]
    clip.export(out_path, format="wav")
    return out_path


def stitch_segments(segment_wavs: List[tuple[float, float, str]], total_duration: float, out_path: str) -> str:
    """
    segment_wavs: list of (start_time_seconds, end_time_seconds, wav_file_path).
    Each clip has already been time-fit to roughly its slot by fit_duration(),
    but as a hard guarantee against overlap (e.g. if a line couldn't be
    compressed enough), it's also hard-trimmed to its slot length here
    before being placed — so segments can never bleed into the next one.
    """
    canvas = AudioSegment.silent(duration=int(total_duration * 1000) + 1000)
    for start, end, wav_path in segment_wavs:
        piece = AudioSegment.from_file(wav_path)
        slot_ms = max(int((end - start) * 1000), 100)
        if len(piece) > slot_ms:
            piece = piece[:slot_ms]
        canvas = canvas.overlay(piece, position=int(start * 1000))
    canvas.export(out_path, format="wav")
    return out_path


def mux_audio_into_video(video_path: str, new_audio_path: str, out_video_path: str) -> str:
    from moviepy.editor import VideoFileClip, AudioFileClip
    video = VideoFileClip(video_path)
    audio = AudioFileClip(new_audio_path)
    final = video.set_audio(audio)
    final.write_videofile(
        out_video_path,
        codec="libx264",
        audio_codec="aac",
        verbose=False,
        logger=None,
    )
    video.close()
    audio.close()
    return out_video_path
