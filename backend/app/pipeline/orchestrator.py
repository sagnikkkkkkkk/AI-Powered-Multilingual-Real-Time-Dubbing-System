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
from . import asr, translate, tts, video_utils, lipsync, gender_detect, separation, keywords


STAGE_NAMES = [
    "mp4_to_mp3",
    "audio_to_text",
    "extract_keywords",
    "translate_keywords",
    "form_sentence",
    "text_to_mp3",
    "finetune_mp3",
    "final_video",
]


def run_pipeline(job_id: str, video_path: str, target_language: str, voice_gender: str = "auto", preserve_background: bool = True) -> None:
    try:
        jobs.update_job(job_id, overall_status="processing")
        work_dir = OUTPUT_DIR / job_id
        work_dir.mkdir(parents=True, exist_ok=True)

        # --- Stage 1: MP4 -> MP3 (also isolates background music if enabled) ---
        jobs.update_stage(job_id, "mp4_to_mp3", "running")
        raw_audio_mp3 = str(work_dir / "original_audio.mp3")
        video_utils.extract_audio(video_path, raw_audio_mp3)

        vocals_audio = raw_audio_mp3
        background_audio = None
        if preserve_background and ENABLE_BACKGROUND_PRESERVATION:
            sep_result = separation.separate_vocals(raw_audio_mp3, work_dir)
            if sep_result:
                vocals_audio, background_audio = sep_result
                jobs.update_job(job_id, background_preserved=True)
            else:
                jobs.update_job(job_id, background_preserved=False)
        else:
            jobs.update_job(job_id, background_preserved=False)
        jobs.update_stage(job_id, "mp4_to_mp3", "done", "MP3 extracted" + (" + background isolated" if background_audio else ""))

        # --- Stage 2: Audio -> Text ---
        jobs.update_stage(job_id, "audio_to_text", "running")
        segments = asr.transcribe(vocals_audio)
        transcript = " ".join(s.text for s in segments)
        jobs.update_job(job_id, transcript=transcript)

        reference_clip = str(work_dir / "reference.wav")
        video_utils.extract_reference_clip(vocals_audio, reference_clip)
        gender_result = gender_detect.detect_gender(reference_clip)
        jobs.update_job(job_id, detected_gender=gender_result.gender, gender_confidence=gender_result.confidence)
        resolved_gender = gender_result.gender if voice_gender == "auto" else voice_gender
        jobs.update_job(job_id, used_voice_gender=resolved_gender)
        jobs.update_stage(job_id, "audio_to_text", "done", f"{len(segments)} segments transcribed")

        # --- Stage 3: Extract keywords (source language) ---
        jobs.update_stage(job_id, "extract_keywords", "running")
        segment_keywords = [keywords.extract_keywords(s.text) for s in segments]
        flat_source_kw = sorted(set(k for kw in segment_keywords for k in kw))
        jobs.update_job(job_id, keywords_source=", ".join(flat_source_kw))
        jobs.update_stage(job_id, "extract_keywords", "done", f"{len(flat_source_kw)} unique keywords found")

        # --- Stage 4: Translate keywords ---
        jobs.update_stage(job_id, "translate_keywords", "running")
        translated_keywords = [keywords.translate_keywords(kw, target_language) for kw in segment_keywords]
        flat_translated_kw = sorted(set(k for kw in translated_keywords for k in kw))
        jobs.update_job(job_id, keywords_translated=", ".join(flat_translated_kw))
        jobs.update_stage(job_id, "translate_keywords", "done")

        # --- Stage 5: Form sentence (full, grammatically correct translation) ---
        jobs.update_stage(job_id, "form_sentence", "running")
        translated_segments = translate.translate_segments(segments, target_language)
        full_translation = " ".join(s.translated_text for s in translated_segments)
        jobs.update_job(job_id, translation=full_translation)
        jobs.update_stage(job_id, "form_sentence", "done")

        # --- Stage 6: Text -> MP3 ---
        jobs.update_stage(job_id, "text_to_mp3", "running")
        raw_mp3_paths = []
        for i, seg in enumerate(translated_segments):
            raw_seg = work_dir / f"seg_{i:03d}_raw.mp3"
            pace = next((s.pace for s in segments if s.start == seg.start), 1.0)
            tts.synthesize(
                text=seg.translated_text, lang=target_language, out_path=raw_seg,
                reference_audio=reference_clip, pace=pace, gender=resolved_gender,
            )
            raw_mp3_paths.append(raw_seg)
        jobs.update_stage(job_id, "text_to_mp3", "done", f"{len(raw_mp3_paths)} clips synthesized ({resolved_gender} voice)")

        # --- Stage 7: Fine-tune MP3 (time-fit each clip so nothing overlaps) ---
        jobs.update_stage(job_id, "finetune_mp3", "running")
        seg_wavs = []
        for i, seg in enumerate(translated_segments):
            next_start = translated_segments[i + 1].start if i + 1 < len(translated_segments) else seg.end
            slot_end = max(next_start, seg.end)
            slot_duration = max(slot_end - seg.start, 0.3)
            fitted_seg = work_dir / f"seg_{i:03d}_finetuned.mp3"
            video_utils.fit_duration(str(raw_mp3_paths[i]), slot_duration, str(fitted_seg))
            seg_wavs.append((seg.start, slot_end, str(fitted_seg)))
        jobs.update_stage(job_id, "finetune_mp3", "done", "timing fitted, overlap-safe")

        # --- Stage 8: Final dubbed video ---
        jobs.update_stage(job_id, "final_video", "running")
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

        if ENABLE_LIPSYNC:
            lipsynced = str(work_dir / "dubbed_output_lipsync.mp4")
            lipsync.run_lipsync(final_video, final_audio, lipsynced)
            final_video = lipsynced

        jobs.update_stage(job_id, "final_video", "done")
        jobs.update_job(job_id, overall_status="completed", output_path=final_video)

    except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
        jobs.update_job(job_id, overall_status="failed", error=str(exc))
        for name in STAGE_NAMES:
            job = jobs.get_job(job_id)
            if job and any(s.name == name and s.status == "running" for s in job.stages):
                jobs.update_stage(job_id, name, "error", str(exc))
