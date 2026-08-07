"""
AI-Based Native Language Dubbing System — backend API.

Run with:
    uvicorn main:app --reload --port 8000

Endpoints:
    POST /api/upload            -> upload a video, get a job_id
    POST /api/dub                -> start the dubbing pipeline for a job
    GET  /api/status/{job_id}    -> poll pipeline progress
    GET  /api/download/{job_id}  -> download the finished dubbed video
    GET  /api/languages          -> list supported target languages
"""
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import UPLOAD_DIR, SUPPORTED_LANGUAGES
from app.schemas import JobStatus, StageStatus, DubRequest
from app import jobs
from app.pipeline.orchestrator import run_pipeline, STAGE_NAMES

STAGE_LABELS = {
    "separate": "Separating vocals & music",
    "asr": "Transcribing speech",
    "translate": "Translating dialogue",
    "voice_clone": "Synthesizing dubbed voice",
    "prosody": "Matching emotion & pacing",
    "mux": "Rebuilding video",
    "lipsync": "Lip-sync realignment",
}

app = FastAPI(title="AI Native-Language Dubbing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your frontend origin before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/languages")
def list_languages():
    return SUPPORTED_LANGUAGES


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{job_id}_{file.filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    job = JobStatus(
        job_id=job_id,
        filename=file.filename,
        target_language="",
        overall_status="queued",
        stages=[StageStatus(name=n, label=STAGE_LABELS[n], status="pending") for n in STAGE_NAMES],
    )
    jobs.create_job(job)
    return {"job_id": job_id, "video_path": str(dest)}


@app.post("/api/dub")
def start_dubbing(req: DubRequest, background_tasks: BackgroundTasks):
    job = jobs.get_job(req.job_id)
    if not job:
        raise HTTPException(404, "job not found — upload a video first")
    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {req.target_language}")

    matches = list(UPLOAD_DIR.glob(f"{req.job_id}_*"))
    if not matches:
        raise HTTPException(404, "uploaded file missing on disk")
    video_path = str(matches[0])

    jobs.update_job(req.job_id, target_language=req.target_language)
    background_tasks.add_task(
        run_pipeline, req.job_id, video_path, req.target_language,
        req.voice_gender, req.preserve_background,
    )
    return {"status": "started", "job_id": req.job_id}


@app.get("/api/status/{job_id}", response_model=JobStatus)
def get_status(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.get("/api/download/{job_id}")
def download_result(job_id: str):
    job = jobs.get_job(job_id)
    if not job or not job.output_path:
        raise HTTPException(404, "no finished output for this job yet")
    path = Path(job.output_path)
    if not path.exists():
        raise HTTPException(404, "output file missing on disk")
    return FileResponse(path, media_type="video/mp4", filename=f"dubbed_{job.filename}")


# Serve the frontend (index.html + assets) from the same server so the whole
# app can be launched with a single `uvicorn main:app` command.
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
