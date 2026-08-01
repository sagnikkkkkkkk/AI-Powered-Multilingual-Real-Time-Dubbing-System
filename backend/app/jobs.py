"""
Very small in-memory job store.

For a real deployment, swap this for Redis or a database table — the
interface (get/set/update) is intentionally tiny so that swap is a
one-file change.
"""
import threading
from typing import Dict
from .schemas import JobStatus

_lock = threading.Lock()
_jobs: Dict[str, JobStatus] = {}


def create_job(job: JobStatus) -> None:
    with _lock:
        _jobs[job.job_id] = job


def get_job(job_id: str) -> JobStatus | None:
    with _lock:
        return _jobs.get(job_id)


def update_job(job_id: str, **fields) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)


def update_stage(job_id: str, stage_name: str, status: str, detail: str | None = None) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        for stage in job.stages:
            if stage.name == stage_name:
                stage.status = status
                if detail:
                    stage.detail = detail
                break
