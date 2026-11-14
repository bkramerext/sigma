"""Experimental outbound Personal ChatGPT companion bridge.

The control plane NEVER receives OpenAI bearer credentials. This bounded
single-process prototype is only enabled with an explicit environment flag.
Production needs persistent fenced queues and cross-worker synchronization
before general research execution is enabled.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any

from sigma.projects import ProjectError

_PAIR_SECONDS = 180
_LIVE_SECONDS = 35
_MAX_REQUEST_CHARS = 4000
_MAX_RESULT_CHARS = 16000
_LOCK = RLock()


@dataclass
class Pair:
    subject: str
    expires: float


@dataclass
class Worker:
    subject: str
    last_seen: float
    account_label: str = ""
    provider_ready: bool = False


@dataclass
class Job:
    subject: str
    prompt: str
    id: str
    status: str = "queued"
    response: str = ""
    model: str = ""
    created: float = 0.0


_pairs: dict[str, Pair] = {}
_workers: dict[str, Worker] = {}
_jobs: dict[str, Job] = {}


def enabled() -> bool:
    """Explicit per-runtime switch; ordinary local SIGMA is unchanged."""
    return os.environ.get("SIGMA_PERSONAL_COMPANION_ENABLED", "").strip().lower() in {
        "true",
        "1",
        "yes",
    }


def _need_enabled() -> None:
    if not enabled():
        raise ProjectError("Personal companion prototype is not enabled.")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _prune(now: float) -> None:
    for key, value in list(_pairs.items()):
        if value.expires <= now:
            _pairs.pop(key, None)
    # Do not discard offline worker identities: queued work must not be
    # replayed silently, and status must distinguish offline from unpaired.
    if len(_jobs) > 256:
        for key, value in list(_jobs.items()):
            if value.status in {"completed", "failed"} and now - value.created > 3600:
                _jobs.pop(key, None)


def start_pairing(subject: str) -> dict[str, Any]:
    _need_enabled()
    if not subject or len(subject) > 256:
        raise ProjectError("Verified SIGMA identity is required.")
    now = time.monotonic()
    code = secrets.token_urlsafe(24)
    with _LOCK:
        _prune(now)
        for key, pair in list(_pairs.items()):
            if pair.subject == subject:
                _pairs.pop(key, None)
        _pairs[_hash(code)] = Pair(subject, now + _PAIR_SECONDS)
    return {"code": code, "expires_in_seconds": _PAIR_SECONDS}


def redeem(code: str) -> str:
    _need_enabled()
    if not isinstance(code, str) or len(code) > 200:
        raise ProjectError("Pairing expired or invalid.")
    now = time.monotonic()
    with _LOCK:
        _prune(now)
        pair = _pairs.pop(_hash(code), None)
        if pair is None or pair.expires <= now:
            raise ProjectError("Pairing expired or invalid.")
        token = secrets.token_urlsafe(32)
        # A new companion supersedes the old one for this user, so stale
        # workers cannot steal jobs or signal connected.
        for key, worker in list(_workers.items()):
            if worker.subject == pair.subject:
                _workers.pop(key, None)
        _workers[_hash(token)] = Worker(pair.subject, now)
    return token


def _worker(token: str) -> Worker:
    _need_enabled()
    if not isinstance(token, str) or len(token) < 24 or len(token) > 200:
        raise ProjectError("Companion pairing is not authorized.")
    digest = _hash(token)
    with _LOCK:
        worker = next(
            (value for key, value in _workers.items() if hmac.compare_digest(key, digest)),
            None,
        )
    if worker is None:
        raise ProjectError("Companion pairing is not authorized.")
    return worker


def heartbeat(token: str, *, ready: bool, label: str) -> None:
    worker = _worker(token)
    if not isinstance(ready, bool) or not isinstance(label, str) or len(label) > 200:
        raise ProjectError("Invalid companion status.")
    with _LOCK:
        worker.last_seen = time.monotonic()
        worker.provider_ready = ready
        worker.account_label = label if ready else ""


def status(subject: str) -> dict[str, Any]:
    _need_enabled()
    with _LOCK:
        now = time.monotonic()
        worker = next((w for w in _workers.values() if w.subject == subject), None)
        online = bool(worker and now - worker.last_seen < _LIVE_SECONDS)
        return {
            "paired": worker is not None,
            "online": online,
            "ready": bool(online and worker and worker.provider_ready),
            "account_label": worker.account_label if online and worker else "",
            "queued": sum(j.subject == subject and j.status == "queued" for j in _jobs.values()),
        }


def submit(subject: str, prompt: str) -> str:
    _need_enabled()
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > _MAX_REQUEST_CHARS:
        raise ProjectError("Enter a test prompt of 1–4000 characters.")
    if not status(subject)["ready"]:
        raise ProjectError("Connect the Personal companion and choose a ChatGPT account first.")
    job_id = secrets.token_urlsafe(18)
    with _LOCK:
        if any(
            j.subject == subject and j.status in {"queued", "dispatched"} for j in _jobs.values()
        ):
            raise ProjectError("A Personal companion test is already in progress.")
        _jobs[job_id] = Job(subject, prompt.strip(), job_id, created=time.monotonic())
    return job_id


def next_job(token: str) -> dict[str, str] | None:
    worker = _worker(token)
    with _LOCK:
        worker.last_seen = time.monotonic()
        if not worker.provider_ready:
            return None
        for job in _jobs.values():
            if job.subject == worker.subject and job.status == "queued":
                job.status = "dispatched"
                # One-way dispatch; a lost worker never requeues uncertain calls.
                return {"job_id": job.id, "prompt": job.prompt}
    return None


def complete(token: str, job_id: str, *, result: str, model: str, failed: bool = False) -> None:
    worker = _worker(token)
    if (
        not isinstance(job_id, str)
        or not isinstance(result, str)
        or not isinstance(model, str)
        or len(result) > _MAX_RESULT_CHARS
        or len(model) > 120
        or not isinstance(failed, bool)
    ):
        raise ProjectError("Invalid companion result.")
    with _LOCK:
        job = _jobs.get(job_id)
        if job is None or job.subject != worker.subject or job.status != "dispatched":
            raise ProjectError("This test request is not assigned to this companion.")
        job.status = "failed" if failed else "completed"
        job.response = result
        job.model = model
        worker.last_seen = time.monotonic()


def result(subject: str, job_id: str) -> dict[str, str]:
    _need_enabled()
    with _LOCK:
        job = _jobs.get(job_id)
        if job is None or job.subject != subject:
            raise ProjectError("Personal test request is unavailable.")
        return {
            "job_id": job.id,
            "status": job.status,
            "response": job.response if job.status in {"completed", "failed"} else "",
            "model": job.model if job.status in {"completed", "failed"} else "",
        }


def disconnect(token: str) -> None:
    worker = _worker(token)
    with _LOCK:
        for key, value in list(_workers.items()):
            if value is worker:
                _workers.pop(key, None)


def clear_for_tests() -> None:
    with _LOCK:
        _pairs.clear()
        _workers.clear()
        _jobs.clear()
