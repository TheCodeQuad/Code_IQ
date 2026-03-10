"""
Repository API router.

Endpoints
---------
POST /api/repos/upload            – Clone a GitHub repo and create a DB record for a user.
GET  /api/repos                   – List all repos belonging to a user.
GET  /api/repos/{id}              – Get full details of a single repo.
DELETE /api/repos/{id}            – Delete a repo record (and optionally its cloned files).
POST /api/repos/{id}/generate     – Kick off the documentation pipeline (background).
GET  /api/repos/{id}/status       – Poll current pipeline progress.
"""

import asyncio
import os
import re
import shutil
import stat
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from backend.models.repository import (
    AgentLog,
    RepoDetail,
    RepoStatus,
    RepoSummary,
    RepoUploadRequest,
    RepositoryDoc,
)
from backend.utils.db import get_repos_collection, update_repo_status, update_agent_log
from backend.utils.logger import get_logger

router = APIRouter(prefix="/api/repos", tags=["repositories"])
logger = get_logger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]            # Code_IQ/
CLONE_DIR = PROJECT_ROOT / "data" / "input" / "repositories"  # where repos are cloned
CLONE_DIR.mkdir(parents=True, exist_ok=True)


def _extract_repo_name(repo_url: str) -> str:
    """Derive a filesystem-safe repo name from a GitHub URL."""
    url = repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    name = url.split("/")[-1]
    return re.sub(r"[^\w\-]", "_", name)


def _handle_remove_readonly(func, path, _exc_info):
    """Windows: clear read-only flag before retrying delete."""
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise


def _clone_repo(repo_url: str) -> str:
    """Clone a git repo into CLONE_DIR/<repo_name> and return the path."""
    repo_name = _extract_repo_name(repo_url)
    dest = CLONE_DIR / repo_name
    if dest.exists():
        shutil.rmtree(str(dest), onerror=_handle_remove_readonly)
    subprocess.run(
        ["git", "clone", repo_url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    return str(dest)


def _count_files_and_lines(repo_path: str) -> tuple[int, int]:
    """Walk the cloned repo and count source files + total lines."""
    source_exts = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".java",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs",
        ".rb", ".php", ".swift", ".kt", ".scala",
    }
    file_count = 0
    total_lines = 0
    for root, _dirs, files in os.walk(repo_path):
        # Skip hidden dirs and common non-source dirs
        parts = Path(root).parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__", "venv", ".venv", "dist", "build") for p in parts):
            continue
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in source_exts:
                file_count += 1
                try:
                    with open(os.path.join(root, fname), "r", encoding="utf-8", errors="ignore") as f:
                        total_lines += sum(1 for _ in f)
                except Exception:
                    pass
    return file_count, total_lines


def _detect_language(repo_path: str) -> str:
    """Return the dominant programming language based on file extensions."""
    ext_map = {
        ".py": "python", ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript", ".java": "java",
        ".go": "go", ".rs": "rust", ".rb": "ruby", ".cpp": "cpp",
        ".c": "c", ".cs": "csharp", ".php": "php",
    }
    counts: dict[str, int] = {}
    for root, _dirs, files in os.walk(repo_path):
        parts = Path(root).parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__", "venv", ".venv") for p in parts):
            continue
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            lang = ext_map.get(ext)
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "unknown"
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _repo_doc_to_summary(doc: dict) -> dict:
    """Convert a raw MongoDB document to a RepoSummary-compatible dict."""
    overall = None
    if doc.get("evaluation") and doc["evaluation"].get("overall_score") is not None:
        overall = doc["evaluation"]["overall_score"]
    return {
        "id": str(doc["_id"]),
        "repo_name": doc["repo_name"],
        "repo_url": doc.get("repo_url"),
        "language": doc.get("language"),
        "file_count": doc.get("file_count", 0),
        "status": doc.get("status", "pending"),
        "progress_percent": doc.get("progress_percent", 0),
        "current_agent": doc.get("current_agent"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "completed_at": doc.get("completed_at"),
        "overall_score": overall,
    }


def _repo_doc_to_detail(doc: dict) -> dict:
    """Convert a raw MongoDB document to a RepoDetail-compatible dict."""
    base = _repo_doc_to_summary(doc)
    base.update({
        "repo_local_path": doc.get("repo_local_path"),
        "total_lines": doc.get("total_lines", 0),
        "agent_logs": doc.get("agent_logs", []),
        "stats": doc.get("stats"),
        "documentation": doc.get("documentation"),
        "evaluation": doc.get("evaluation"),
        "error_message": doc.get("error_message"),
    })
    return base


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/upload", status_code=201)
async def upload_repo(req: RepoUploadRequest):
    """
    Clone a GitHub repository and persist a record in the `repositories` collection.
    Returns the new repo_id so the frontend can redirect to the analysis page.
    """
    # 1. Validate user_id looks like a Mongo ObjectId
    if not ObjectId.is_valid(req.user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    repo_name = _extract_repo_name(req.repo_url)

    # 2. Clone the repo
    try:
        repo_path = _clone_repo(req.repo_url)
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to clone repository: {e.stderr or str(e)}",
        )

    # 3. Gather basic metadata from the cloned files
    file_count, total_lines = _count_files_and_lines(repo_path)
    language = _detect_language(repo_path)

    # 4. Build the document
    now = datetime.utcnow().isoformat()
    doc = RepositoryDoc(
        user_id=req.user_id,
        repo_name=repo_name,
        repo_url=req.repo_url,
        repo_local_path=repo_path,
        language=language,
        file_count=file_count,
        total_lines=total_lines,
        status=RepoStatus.PENDING,
        created_at=now,
        updated_at=now,
    )

    # 5. Insert into MongoDB
    collection = await get_repos_collection()
    result = await collection.insert_one(doc.model_dump())

    return {
        "success": True,
        "repo_id": str(result.inserted_id),
        "repo_name": repo_name,
        "language": language,
        "file_count": file_count,
        "total_lines": total_lines,
    }


@router.get("")
async def list_repos(user_id: str = Query(..., description="User ObjectId")):
    """
    Return all repositories belonging to the given user, newest first.
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    collection = await get_repos_collection()
    cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)

    return {
        "repos": [_repo_doc_to_summary(d) for d in docs],
        "total": len(docs),
    }


@router.get("/{repo_id}")
async def get_repo(repo_id: str):
    """
    Return full details for a single repository.
    """
    if not ObjectId.is_valid(repo_id):
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    collection = await get_repos_collection()
    doc = await collection.find_one({"_id": ObjectId(repo_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")

    return _repo_doc_to_detail(doc)


@router.delete("/{repo_id}")
async def delete_repo(repo_id: str):
    """
    Delete a repository record and optionally remove cloned files.
    """
    if not ObjectId.is_valid(repo_id):
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    collection = await get_repos_collection()
    doc = await collection.find_one({"_id": ObjectId(repo_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Remove cloned directory if it exists
    local_path = doc.get("repo_local_path")
    if local_path and os.path.isdir(local_path):
        try:
            shutil.rmtree(local_path, onerror=_handle_remove_readonly)
        except Exception:
            pass  # best-effort cleanup

    await collection.delete_one({"_id": ObjectId(repo_id)})

    return {"success": True, "message": f"Repository {repo_id} deleted"}


# ── Pipeline endpoints ───────────────────────────────────────────────

# Keep track of in-flight pipelines so we don't double-start.
_running_pipelines: set[str] = set()


def _run_pipeline_thread(repo_id: str, repo_path: str, loop: asyncio.AbstractEventLoop):
    """
    Runs the synchronous pipeline in a background thread.
    Fires async DB updates through the provided event loop.
    """
    from backend.pipeline import run_pipeline  # lazy import avoids circular

    def status_callback(agent: str, status: str, progress: int, message: str):
        """Bridge: sync callback → async DB update via loop."""
        asyncio.run_coroutine_threadsafe(
            update_repo_status(
                repo_id,
                status=agent if status == "in_progress" else status,
                current_agent=agent,
                progress_percent=progress,
            ),
            loop,
        )

    try:
        result = run_pipeline(repo_path, status_callback=status_callback)

        # Extract statistics and evaluation summary
        stats = result.get("statistics", {})
        doc_count = len(result.get("documentation", []))

        asyncio.run_coroutine_threadsafe(
            update_repo_status(
                repo_id,
                status="completed",
                current_agent=None,
                progress_percent=100,
                extra_fields={
                    "completed_at": datetime.utcnow().isoformat(),
                    "stats": stats,
                    "documentation_count": doc_count,
                },
            ),
            loop,
        )
    except Exception as exc:
        logger.error(f"Pipeline failed for {repo_id}: {exc}", exc_info=True)
        asyncio.run_coroutine_threadsafe(
            update_repo_status(
                repo_id,
                status="failed",
                error_message=str(exc)[:500],
                current_agent=None,
            ),
            loop,
        )
    finally:
        _running_pipelines.discard(repo_id)


@router.post("/{repo_id}/generate", status_code=202)
async def generate_docs(repo_id: str):
    """
    Start the documentation-generation pipeline for a repository.
    Returns immediately — poll ``GET /api/repos/{repo_id}/status`` for progress.
    """
    if not ObjectId.is_valid(repo_id):
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    if repo_id in _running_pipelines:
        raise HTTPException(status_code=409, detail="Pipeline already running for this repo")

    collection = await get_repos_collection()
    doc = await collection.find_one({"_id": ObjectId(repo_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo_path = doc.get("repo_local_path")
    if not repo_path or not os.path.isdir(repo_path):
        raise HTTPException(status_code=400, detail="Cloned repository not found on disk")

    # Mark as started
    _running_pipelines.add(repo_id)
    await update_repo_status(
        repo_id,
        status="parsing",
        current_agent="navigator",
        progress_percent=0,
    )

    # Launch the pipeline in a background thread
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(repo_id, repo_path, loop),
        daemon=True,
    )
    thread.start()

    return {
        "success": True,
        "repo_id": repo_id,
        "message": "Pipeline started",
    }


@router.get("/{repo_id}/status")
async def get_repo_status(repo_id: str):
    """
    Return the current pipeline progress for a repository.
    Lightweight endpoint designed for polling.
    """
    if not ObjectId.is_valid(repo_id):
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    collection = await get_repos_collection()
    doc = await collection.find_one(
        {"_id": ObjectId(repo_id)},
        {
            "status": 1,
            "progress_percent": 1,
            "current_agent": 1,
            "agent_logs": 1,
            "error_message": 1,
            "stats": 1,
            "completed_at": 1,
            "updated_at": 1,
        },
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")

    return {
        "repo_id": repo_id,
        "status": doc.get("status", "pending"),
        "progress_percent": doc.get("progress_percent", 0),
        "current_agent": doc.get("current_agent"),
        "agent_logs": doc.get("agent_logs", []),
        "error_message": doc.get("error_message"),
        "stats": doc.get("stats"),
        "completed_at": doc.get("completed_at"),
        "updated_at": doc.get("updated_at"),
    }
