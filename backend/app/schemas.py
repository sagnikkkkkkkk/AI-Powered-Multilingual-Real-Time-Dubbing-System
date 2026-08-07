from pydantic import BaseModel
from typing import Optional, List


class DubRequest(BaseModel):
    job_id: str
    target_language: str  # e.g. "hi", "ta", "fr"
    preserve_emotion: bool = True
    voice_gender: str = "auto"  # "auto" | "male" | "female"
    preserve_background: bool = True  # keep original background music/ambience

class StageStatus(BaseModel):
    name: str
    label: str
    status: str  # pending | running | done | error
    detail: Optional[str] = None


class JobStatus(BaseModel):
    job_id: str
    filename: str
    target_language: str
    overall_status: str  # queued | processing | completed | failed
    stages: List[StageStatus]
    transcript: Optional[str] = None
    translation: Optional[str] = None
    output_path: Optional[str] = None
    error: Optional[str] = None
    detected_gender: Optional[str] = None
    gender_confidence: Optional[str] = None
    used_voice_gender: Optional[str] = None
    background_preserved: Optional[bool] = None
