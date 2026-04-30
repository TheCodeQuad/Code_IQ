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
from datetime import timezone
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
from backend.utils.paths import DATA_ROOT
from backend.utils.progress_stream import format_sse_event, progress_broadcaster

router = APIRouter(prefix="/api/repos", tags=["repositories"])
logger = get_logger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]            # Code_IQ/
CLONE_DIR = DATA_ROOT / "input" / "repositories"  # where repos are cloned
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


def _clone_repo(repo_url: str, github_token: Optional[str] = None) -> str:
    """Clone a git repo into CLONE_DIR/<repo_name> and return the path.
    
    Args:
        repo_url: URL of the repository to clone
        github_token: GitHub token for private repositories (optional)
    """
    repo_name = _extract_repo_name(repo_url)
    dest = CLONE_DIR / repo_name
    if dest.exists():
        shutil.rmtree(str(dest), onerror=_handle_remove_readonly)
    
    # If github_token provided, inject it into the URL for private repo access
    clone_url = repo_url
    if github_token and "github.com" in repo_url and not repo_url.startswith("git@"):
        # Convert https://github.com/owner/repo.git to https://token@github.com/owner/repo.git
        clone_url = repo_url.replace("https://github.com", f"https://{github_token}@github.com")
    
    try:
        subprocess.run(
            ["git", "clone", clone_url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"Failed to clone {repo_url}: {error_msg}")
        raise
    
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

    # 2. Get user's GitHub token for private repo access (if available)
    github_token = None
    try:
        from backend.utils.db import get_users_collection
        users_col = await get_users_collection()
        user = await users_col.find_one({"_id": ObjectId(req.user_id)})
        if user:
            github_token = user.get("github_access_token")
            if github_token:
                logger.info(f"Using GitHub token for user {req.user_id}")
    except Exception as e:
        logger.warning(f"Could not retrieve GitHub token for user: {e}")

    # 3. Clone the repo
    try:
        repo_path = _clone_repo(req.repo_url, github_token=github_token)
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or str(e)
        logger.error(f"Clone failed: {error_msg}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to clone repository: {error_msg}",
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

    # Resolve candidate clone directories to delete.
    # This handles historical records where repo_local_path may be stale after
    # data-root migrations (e.g., from <app>/data to ../data).
    candidate_dirs: list[Path] = []

    local_path = doc.get("repo_local_path")
    if local_path:
        candidate_dirs.append(Path(local_path))

    repo_name = doc.get("repo_name")
    if repo_name:
        candidate_dirs.append(CLONE_DIR / repo_name)

    repo_url = doc.get("repo_url")
    if repo_url:
        candidate_dirs.append(CLONE_DIR / _extract_repo_name(repo_url))

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique_dirs: list[Path] = []
    for path in candidate_dirs:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique_dirs.append(path)

    # Remove all matching clone directories before deleting DB metadata.
    cleanup_errors: list[str] = []
    removed_paths: list[str] = []
    for path in unique_dirs:
        if not path.is_dir():
            continue
        try:
            shutil.rmtree(str(path), onerror=_handle_remove_readonly)
            removed_paths.append(str(path))
        except Exception as exc:
            cleanup_errors.append(f"{path}: {exc}")

    if cleanup_errors:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to delete repository files; metadata was not removed",
                "errors": cleanup_errors,
            },
        )

    await collection.delete_one({"_id": ObjectId(repo_id)})

    return {
        "success": True,
        "message": f"Repository {repo_id} deleted",
        "removed_paths": removed_paths,
    }


# ── Pipeline endpoints ───────────────────────────────────────────────

# Keep track of in-flight pipelines so we don't double-start.
_running_pipelines: set[str] = set()


class GenerateDocsRequest(BaseModel):
    """Optional payload for pipeline generation options."""
    demo_mode: bool = False


async def _publish_pipeline_event(repo_id: str, event: dict[str, Any]) -> None:
    """Publish a progress event to SSE subscribers."""
    payload = dict(event)
    payload.setdefault("repo_id", repo_id)
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    await progress_broadcaster.publish(repo_id, payload)


def _run_pipeline_thread(
    repo_id: str,
    repo_path: str,
    loop: asyncio.AbstractEventLoop,
    demo_mode: bool = False,
):
    """
    Runs the synchronous pipeline in a background thread.
    Fires async DB updates through the provided event loop.
    """
    from backend.pipeline import run_pipeline  # lazy import avoids circular

    def status_callback(
        agent: str,
        status: str,
        progress: int,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ):
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
        event_payload = {
            "event_type": "pipeline_progress",
            "agent": agent,
            "status": status,
            "progress_percent": progress,
            "message": message,
            **(details or {}),
        }
        asyncio.run_coroutine_threadsafe(
            _publish_pipeline_event(repo_id, event_payload),
            loop,
        )

    try:
        result = run_pipeline(repo_path, status_callback=status_callback, demo_mode=demo_mode)

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
                    "demo_mode": bool(result.get("demo_mode", demo_mode)),
                },
            ),
            loop,
        )
        asyncio.run_coroutine_threadsafe(
            _publish_pipeline_event(
                repo_id,
                {
                    "event_type": "pipeline_progress",
                    "agent": "pipeline",
                    "status": "completed",
                    "progress_percent": 100,
                    "message": "Demo analysis completed" if demo_mode else "Pipeline completed",
                    "phase": "finalization",
                    "step_id": "pipeline-completed",
                    "demo_mode": demo_mode,
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
        asyncio.run_coroutine_threadsafe(
            _publish_pipeline_event(
                repo_id,
                {
                    "event_type": "pipeline_progress",
                    "agent": "pipeline",
                    "status": "failed",
                    "progress_percent": 100,
                    "message": str(exc)[:500],
                },
            ),
            loop,
        )
    finally:
        _running_pipelines.discard(repo_id)


@router.post("/{repo_id}/generate", status_code=202)
async def generate_docs(repo_id: str, payload: Optional[GenerateDocsRequest] = None):
    """
    Start the documentation-generation pipeline for a repository.
    Returns immediately — poll ``GET /api/repos/{repo_id}/status`` for progress.
    """
    if not ObjectId.is_valid(repo_id):
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    if repo_id in _running_pipelines:
        raise HTTPException(status_code=409, detail="Pipeline already running for this repo")

    demo_mode = bool(payload.demo_mode) if payload else False

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
    await _publish_pipeline_event(
        repo_id,
        {
            "event_type": "pipeline_progress",
            "agent": "navigator",
            "status": "in_progress",
            "progress_percent": 0,
            "message": "Demo analysis started" if demo_mode else "Pipeline started",
            "phase": "navigator",
            "step_id": "extract-components",
            "demo_mode": demo_mode,
        },
    )

    # Launch the pipeline in a background thread
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(repo_id, repo_path, loop, demo_mode),
        daemon=True,
    )
    thread.start()

    return {
        "success": True,
        "repo_id": repo_id,
        "demo_mode": demo_mode,
        "mode": "demo" if demo_mode else "full",
        "message": "Demo analysis started" if demo_mode else "Pipeline started",
    }


@router.get("/{repo_id}/events")
async def stream_repo_events(repo_id: str, request: Request):
    """Stream live pipeline progress updates via Server-Sent Events."""
    if not ObjectId.is_valid(repo_id):
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    collection = await get_repos_collection()
    doc = await collection.find_one(
        {"_id": ObjectId(repo_id)},
        {
            "status": 1,
            "progress_percent": 1,
            "current_agent": 1,
            "updated_at": 1,
        },
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")

    queue = await progress_broadcaster.subscribe(repo_id)

    async def event_generator():
        try:
            # Initial snapshot lets reconnecting clients restore state quickly.
            initial_event = {
                "event_type": "pipeline_snapshot",
                "repo_id": repo_id,
                "status": doc.get("status", "pending"),
                "progress_percent": doc.get("progress_percent", 0),
                "agent": doc.get("current_agent"),
                "timestamp": doc.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            }
            yield format_sse_event(initial_event, event="snapshot")

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield format_sse_event(event, event="progress")
                except asyncio.TimeoutError:
                    # Keep-alive comment for proxies and browser EventSource.
                    yield ": keepalive\n\n"
        finally:
            await progress_broadcaster.unsubscribe(repo_id, queue)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=headers,
    )


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


# ── File-tree endpoint ───────────────────────────────────────────────

# Directories to skip when building the file tree
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".idea", ".vscode", ".mypy_cache",
    ".pytest_cache", ".tox", "eggs", "*.egg-info",
}

# Source-code extensions we care about
_SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs",
    ".rb", ".php", ".swift", ".kt", ".scala",
    ".css", ".scss", ".html", ".vue", ".svelte",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
    ".sh", ".bat", ".ps1", ".dockerfile",
}


def _build_tree(root_path: str, base_path: str | None = None) -> list[dict]:
    """
    Recursively walk *root_path* and return a JSON-serialisable tree.

    Each node is either:
        { "name": str, "type": "folder", "path": str, "children": [...] }
        { "name": str, "type": "file",   "path": str, "size": int }
    """
    if base_path is None:
        base_path = root_path
    entries: list[dict] = []

    try:
        items = sorted(os.listdir(root_path), key=lambda s: (not os.path.isdir(os.path.join(root_path, s)), s.lower()))
    except PermissionError:
        return entries

    for name in items:
        full = os.path.join(root_path, name)
        rel = os.path.relpath(full, base_path).replace("\\", "/")

        if os.path.isdir(full):
            if name in _SKIP_DIRS or name.startswith("."):
                continue
            children = _build_tree(full, base_path)
            entries.append({
                "name": name,
                "type": "folder",
                "path": rel,
                "children": children,
            })
        else:
            ext = os.path.splitext(name)[1].lower()
            if ext in _SOURCE_EXTS or name.lower() in ("makefile", "dockerfile", "rakefile", "gemfile"):
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                entries.append({
                    "name": name,
                    "type": "file",
                    "path": rel,
                    "size": size,
                })

    return entries


@router.get("/{repo_id}/tree")
async def get_repo_tree(repo_id: str):
    """
    Return the directory tree of the cloned repository.
    The tree only includes source-relevant files and skips common
    non-source directories (.git, node_modules, etc.).
    """
    if not ObjectId.is_valid(repo_id):
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    collection = await get_repos_collection()
    doc = await collection.find_one(
        {"_id": ObjectId(repo_id)},
        {"repo_local_path": 1, "repo_name": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo_path = doc.get("repo_local_path")
    if not repo_path or not os.path.isdir(repo_path):
        raise HTTPException(status_code=404, detail="Cloned repository not found on disk")

    tree = _build_tree(repo_path)

    return {
        "repo_id": repo_id,
        "repo_name": doc.get("repo_name", ""),
        "root_path": repo_path,
        "tree": tree,
    }


@router.get("/{repo_id}/file")
async def get_repo_file(
    repo_id: str, 
    path: str = Query(..., description="Relative file path within the repo"),
    documented: bool = Query(False, description="Return documented version if available")
):
    """
    Return the contents of a single file from the cloned repository.
    The `path` parameter must be a relative path within the repo root.
    If `documented=true`, returns the documented version from the analysis results (if available).
    Otherwise returns the original file from disk.
    """
    if not ObjectId.is_valid(repo_id):
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    collection = await get_repos_collection()
    doc = await collection.find_one(
        {"_id": ObjectId(repo_id)},
        {"repo_local_path": 1, "documentation": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo_path = doc.get("repo_local_path")
    if not repo_path or not os.path.isdir(repo_path):
        raise HTTPException(status_code=404, detail="Cloned repository not found on disk")

    # Resolve and validate that target is within repo_path (prevent path traversal)
    target = os.path.normpath(os.path.join(repo_path, path))
    if not target.startswith(os.path.normpath(repo_path)):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(500_000)  # Cap at 500KB
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read file: {e}")

    # If documented=true, try to find the documented version in the documentation array
    documented_content = None
    if documented and doc.get("documentation"):
        # Search for this file in the documentation array
        for doc_item in doc["documentation"]:
            if doc_item.get("file_path") == path or doc_item.get("path") == path:
                documented_content = doc_item.get("content") or doc_item.get("documented_content")
                break

    return {
        "path": path,
        "content": documented_content if documented else content,
        "original": content if documented else None,
        "size": os.path.getsize(target),
        "has_documented": documented_content is not None if documented else False,
    }
