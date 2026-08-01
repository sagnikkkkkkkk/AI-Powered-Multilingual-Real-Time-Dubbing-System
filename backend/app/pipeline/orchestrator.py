"""
Wires all stages together and keeps the job store updated so the
frontend can poll for live progress.

Changes from the first version, addressing the reported issues:
  1. Overlap: each synthesized segment is now time-fit (video_utils.fit_duration)
     to the gap before the NEXT segment starts, not just its own original
     duration, and stitch_segments hard-trims as a second safety net.
  2. Gender detection: gender_detect.detect_gender() actually analyzes the
     source voice's pitch now, instead of nothing happening at all.
  3. Male/female selection: voice_gender is threaded through from the API
     request; "auto" uses the detected gender, otherwise the user's choice
     is used outright, passed to tts.synthesize(..., gender=...).
  4. Background music: if separation.py succeeds, ASR/reference/TTS all
     work against the isolated vocals track, and the final mix layers the
     new dubbed vocals back onto the ORIGINAL background track rather than
     replacing the whole audio. Falls back to the old full-replace
     behavior automatically if separation isn't available.
"""
from pathlib import Path
from .. import jobs
from ..config import OUTPUT_DIR, ENABLE_LIPSYNC, ENABLE_BACKGROUND_PRESERVATION
from . import asr, translate, tts, video_utils, lipsync, gender_detect, separation


STAGE_NAMES = [
    "separate",
    "asr",
    "translate",
    "voice_clone",
    "prosody",
    "mux",
    "lipsync",
]


def run_pipeline(job_id: str, video_path: str, target_language: str, voice_gender: str = "auto") -> None:
    try:
        jobs.update_job(job_id, overall_status="processing")
        work_dir = OUTPUT_DIR / job_id
        work_dir.mkdir(parents=True, exist_ok=True)

        # --- Stage 0: extract audio, then try to separate vocals/background ---
        raw_audio = str(work_dir / "original_audio.wav")
        video_utils.extract_audio(video_path, raw_audio)

        vocals_audio = raw_audio  # default: no separation, work on the full mix
        background_audio = None

        if ENABLE_BACKGROUND_PRESERVATION:
            jobs.update_stage(job_id, "separate", "running")
            sep_result = separation.separate_vocals(raw_audio, work_dir)
            if sep_result:
                vocals_audio, background_audio = sep_result
                jobs.update_job(job_id, background_preserved=True)
                jobs.update_stage(job_id, "separate", "done", "background music isolated")
            else:
                jobs.update_job(job_id, background_preserved=False)
                jobs.update_stage(
                    job_id, "separate", "done",
                    "separation unavailable — install `demucs` to preserve background music; using full audio replace for now"
                )
        else:
            jobs.update_job(job_id, background_preserved=False)
            jobs.update_stage(job_id, "separate", "done", "disabled in config")

        # --- Stage 1: transcribe the (isolated, if available) vocals ---
        jobs.update_stage(job_id, "asr", "running")
        segments = asr.transcribe(vocals_audio)
        transcript = " ".join(s.text for s in segments)
        jobs.update_job(job_id, transcript=transcript)
        jobs.update_stage(job_id, "asr", "done", f"{len(segments)} segments detected")

        # --- Gender detection on the clean vocal reference clip ---
        reference_clip = str(work_dir / "reference.wav")
        video_utils.extract_reference_clip(vocals_audio, reference_clip)

        gender_result = gender_detect.detect_gender(reference_clip)
        jobs.update_job(job_id, detected_gender=gender_result.gender, gender_confidence=gender_result.confidence)

        resolved_gender = gender_result.gender if voice_gender == "auto" else voice_gender
        jobs.update_job(job_id, used_voice_gender=resolved_gender)

        # --- Stage 2: duration-aware translation ---
        jobs.update_stage(job_id, "translate", "running")
        translated_segments = translate.translate_segments(segments, target_language)
        full_translation = " ".join(s.translated_text for s in translated_segments)
        jobs.update_job(job_id, translation=full_translation)
        jobs.update_stage(job_id, "translate", "done")

        # --- Stage 3+4: TTS with the resolved voice gender, then fit to slot ---
        jobs.update_stage(job_id, "voice_clone", "running")

        seg_wavs = []  # (start, end, fitted_wav_path)
        for i, seg in enumerate(translated_segments):
            # Slot = up to the NEXT segment's start (not just this segment's
            # own end) — this is what actually prevents overlap even when
            # there's a natural gap/pause between lines in the original.
            next_start = translated_segments[i + 1].start if i + 1 < len(translated_segments) else seg.end
            slot_end = max(next_start, seg.end)
            slot_duration = max(slot_end - seg.start, 0.3)

            raw_seg = work_dir / f"seg_{i:03d}_raw.wav"
            pace = next((s.pace for s in segments if s.start == seg.start), 1.0)
            tts.synthesize(
                text=seg.translated_text,
                lang=target_language,
                out_path=raw_seg,
                reference_audio=reference_clip,
                pace=pace,
                gender=resolved_gender,
            )

            fitted_seg = work_dir / f"seg_{i:03d}_fit.wav"
            video_utils.fit_duration(str(raw_seg), slot_duration, str(fitted_seg))
            seg_wavs.append((seg.start, slot_end, str(fitted_seg)))

        jobs.update_stage(job_id, "voice_clone", "done", f"{len(seg_wavs)} clips synthesized ({resolved_gender} voice)")
        jobs.update_stage(job_id, "prosody", "done", "pace matched, time-fit to slot")

        # --- Stage 5: stitch dubbed vocals, mix with background, mux onto video ---
        jobs.update_stage(job_id, "mux", "running")
        total_duration = segments[-1].end if segments else 0
        dubbed_vocals = str(work_dir / "dubbed_vocals.wav")
        video_utils.stitch_segments(seg_wavs, total_duration, dubbed_vocals)

        if background_audio:
            final_audio = str(work_dir / "dubbed_audio_mixed.wav")
            video_utils.mix_background(dubbed_vocals, background_audio, final_audio)
        else:
            final_audio = dubbed_vocals

        final_video = str(work_dir / "dubbed_output.mp4")
        video_utils.mux_audio_into_video(video_path, final_audio, final_video)
        jobs.update_stage(job_id, "mux", "done")

        # --- Stage 6: optional lip-sync ---
        if ENABLE_LIPSYNC:
            jobs.update_stage(job_id, "lipsync", "running")
            lipsynced = str(work_dir / "dubbed_output_lipsync.mp4")
            lipsync.run_lipsync(final_video, final_audio, lipsynced)
            final_video = lipsynced
            jobs.update_stage(job_id, "lipsync", "done")
        else:
            jobs.update_stage(job_id, "lipsync", "done", "skipped (disabled in config)")

        jobs.update_job(job_id, overall_status="completed", output_path=final_video)

    except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
        jobs.update_job(job_id, overall_status="failed", error=str(exc))
        for name in STAGE_NAMES:
            job = jobs.get_job(job_id)
            if job and any(s.name == name and s.status == "running" for s in job.stages):
                jobs.update_stage(job_id, name, "error", str(exc))
