"""
Analysis API routes.

Endpoints for accessing analysis results and linked repository data.
"""

import re
import io
import json
import zipfile
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
import httpx

from backend.models.repository import RepositoryDoc
from backend.utils.db import get_repos_collection
from backend.utils.logger import get_logger

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
logger = get_logger(__name__)

GITHUB_API_BASE = "https://api.github.com"


def _parse_github_full_name(value: str) -> Optional[str]:
    """Extract owner/repo from common GitHub URL formats."""
    if not value:
        return None

    raw = value.strip()

    # Already owner/repo format
    if re.match(r"^[\w.-]+/[\w.-]+$", raw):
        return raw

    # git@github.com:owner/repo.git
    ssh_match = re.search(r"github\.com:([\w.-]+/[\w.-]+?)(?:\.git)?$", raw)
    if ssh_match:
        return ssh_match.group(1)

    # https://github.com/owner/repo(.git)
    https_match = re.search(r"github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?(?:$|/)", raw)
    if https_match:
        return https_match.group(1)

    return None


def _read_origin_url_from_git_config(repo_local_path: str) -> str:
    """Best-effort origin URL lookup from .git/config for cloned repos."""
    try:
        config_path = Path(repo_local_path) / ".git" / "config"
        if not config_path.exists():
            return ""

        in_origin_block = False
        for line in config_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_origin_block = stripped.lower() == '[remote "origin"]'
                continue
            if in_origin_block and stripped.lower().startswith("url") and "=" in stripped:
                return stripped.split("=", 1)[1].strip()
    except Exception:
        return ""

    return ""


def _extract_repo_linkage(repo_doc: dict) -> tuple[Optional[str], Optional[str]]:
    """Resolve (owner/repo, canonical_repo_url) from heterogeneous repo docs."""
    candidates = [
        repo_doc.get("github_repo_full_name"),
        repo_doc.get("full_name"),
        repo_doc.get("repo_url"),
        repo_doc.get("github_url"),
        repo_doc.get("url"),
        repo_doc.get("github_repo_url"),
        repo_doc.get("clone_url"),
        repo_doc.get("origin_url"),
    ]

    full_name: Optional[str] = None
    repo_url: Optional[str] = None

    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        parsed = _parse_github_full_name(candidate)
        if parsed:
            full_name = parsed
            if "github.com" in candidate:
                repo_url = candidate
            break

    if not full_name:
        repo_local_path = repo_doc.get("repo_local_path")
        if isinstance(repo_local_path, str) and repo_local_path:
            origin_url = _read_origin_url_from_git_config(repo_local_path)
            parsed = _parse_github_full_name(origin_url)
            if parsed:
                full_name = parsed
                repo_url = origin_url

    if full_name and not repo_url:
        repo_url = f"https://github.com/{full_name}"

    return full_name, repo_url


# ── Request Models ──────────────────────────────────────────────────────

class FileChange(BaseModel):
    """A file change to be committed"""
    path: str
    content: str
    action: str = "create"  # create | update | delete


class SafePRRequest(BaseModel):
    """Request to create a PR with a new branch (safe workflow)"""
    analysisId: str
    repo: str  # owner/repo
    title: str
    description: str
    baseBranch: str = "main"
    sourceBranch: str  # The new branch to create (e.g., codeiq/docs-repo-abc123)
    draft: bool = False
    userId: Optional[str] = None
    # File changes to commit
    files: Optional[List[FileChange]] = None
    commitMessage: str = "docs: Add AI-generated documentation via CodeIQ"


# ── Error Types for specific GitHub errors ──────────────────────────────

class PRCreationError:
    BRANCH_EXISTS = "branch_exists"
    NO_WRITE_ACCESS = "no_write_access"
    PROTECTED_BRANCH = "protected_branch"
    MERGE_CONFLICT = "merge_conflict"
    SAME_BRANCH = "same_branch"
    TOKEN_EXPIRED = "token_expired"
    REPO_NOT_FOUND = "repo_not_found"
    RATE_LIMITED = "rate_limited"
    UNKNOWN = "unknown"


def classify_github_error(status_code: int, error_data: dict) -> tuple[str, str]:
    """Classify GitHub API error and return (error_type, user_friendly_message)"""
    message = error_data.get("message", "").lower()
    errors = error_data.get("errors", [])

    if status_code == 401:
        return PRCreationError.TOKEN_EXPIRED, "Your GitHub token has expired. Please reconnect your GitHub account."

    if status_code == 403:
        if "rate limit" in message:
            return PRCreationError.RATE_LIMITED, "GitHub API rate limit exceeded. Please try again later."
        if "push" in message or "write" in message or "protected" in message:
            return PRCreationError.NO_WRITE_ACCESS, "You don't have write access to this repository."
        return PRCreationError.NO_WRITE_ACCESS, "Permission denied. You may not have write access to this repository."

    if status_code == 404:
        return PRCreationError.REPO_NOT_FOUND, "Repository not found. Make sure you have access to this repository."

    if status_code == 422:
        for err in errors:
            err_msg = str(err).lower()
            if "already exists" in err_msg or "reference already exists" in err_msg:
                return PRCreationError.BRANCH_EXISTS, "A branch with this name already exists. Please choose a different branch name."
            if "protected" in err_msg:
                return PRCreationError.PROTECTED_BRANCH, "Cannot push to a protected branch. Please choose a different base branch."
        if "already exists" in message:
            return PRCreationError.BRANCH_EXISTS, "A branch with this name already exists. Please choose a different branch name."

    return PRCreationError.UNKNOWN, error_data.get("message", "An unknown error occurred while creating the PR.")


@router.get("/{analysisId}/repo")
async def get_analysis_repo(analysisId: str, authorization: Optional[str] = Header(None)):
    """
    Get repository information linked to an analysis.
    
    Returns:
    - Repository details (name, owner, branches)
    - Available branches for PR base selection
    
    Accepts optional Authorization header for private repo access.
    """
    try:
        repos_col = await get_repos_collection()
        
        # Try to find by ObjectId first, then by string ID
        repo_doc = None
        if ObjectId.is_valid(analysisId):
            repo_doc = await repos_col.find_one({"_id": ObjectId(analysisId)})
        
        if not repo_doc:
            repo_doc = await repos_col.find_one({"_id": analysisId})
        
        if not repo_doc:
            raise HTTPException(status_code=404, detail="Analysis repository not found")
        
        full_name, repo_url = _extract_repo_linkage(repo_doc)

        if not full_name:
            # Provide detailed error for debugging
            logger.error(f"No GitHub linkage found in repo doc {analysisId}. Available fields: {list(repo_doc.keys())}")
            raise HTTPException(
                status_code=400, 
                detail=f"Analysis doesn't have a GitHub repo URL. Please create a new analysis by selecting a GitHub repository from the connected repos section."
            )

        owner, repo_name = full_name.split("/", 1)
        
        # Fetch branches from GitHub
        branches = ["main", "develop", "staging", "master"]  # Fallback default branches
        default_branch = "main"  # Fallback default branch
        
        try:
            # Prepare headers with optional token
            headers = {}
            if authorization:
                headers["Authorization"] = authorization
                logger.info("[GetRepo] Using provided authorization header")
            
            async with httpx.AsyncClient(timeout=10) as client:
                # First, get repository info to find the actual default branch
                repo_info_response = await client.get(
                    f"{GITHUB_API_BASE}/repos/{full_name}",
                    timeout=10,
                    headers=headers,
                )
                logger.info(f"[GetRepo] Repo info API response status: {repo_info_response.status_code}")
                if repo_info_response.status_code == 200:
                    repo_info = repo_info_response.json()
                    default_branch = repo_info.get("default_branch", "main")
                    logger.info(f"[GetRepo] Found default branch from GitHub: {default_branch}")
                else:
                    logger.warning(f"[GetRepo] Failed to fetch repo info: {repo_info_response.status_code}")
                
                # Try to get branches from GitHub
                branches_response = await client.get(
                    f"{GITHUB_API_BASE}/repos/{full_name}/branches?per_page=50",
                    timeout=10,
                    headers=headers,
                )
                logger.info(f"[GetRepo] Branches API response status: {branches_response.status_code}")
                if branches_response.status_code == 200:
                    branch_data = branches_response.json()
                    logger.info(f"[GetRepo] Fetched {len(branch_data)} branches from GitHub")
                    branches = [b["name"] for b in branch_data]  # Get all branches
                    logger.info(f"[GetRepo] Available branches: {branches}")
                    # Ensure default_branch is in the list
                    if default_branch not in branches:
                        logger.warning(f"[GetRepo] Default branch '{default_branch}' not in branches list, using first branch")
                        default_branch = branches[0] if branches else "main"
                elif branches_response.status_code == 401:
                    logger.warning(f"[GetRepo] Authentication failed when fetching branches: {branches_response.status_code}")
                    # If auth failed, the repo might be private - return what we have
                else:
                    logger.warning(f"[GetRepo] Failed to fetch branches: {branches_response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to fetch branches from GitHub for {full_name}: {e}")
            # Use fallback branches
        
        return {
            "repo": {
                "full_name": full_name,
                "owner": {"login": owner},
                "default_branch": default_branch,
                "url": repo_url or f"https://github.com/{full_name}",
            },
            "branches": branches,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis repo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-pr")
async def create_pull_request(request: dict):
    """
    Create a pull request on GitHub with analysis results.
    
    Request body:
    {
        "analysisId": "analysis-doc-id",
        "repo": "owner/repo-name",
        "title": "PR title",
        "description": "PR description",
        "head": "feature-branch-name",
        "base": "main",
        "draft": false,
        "userId": "optional-user-id-from-session"
    }
    """
    try:
        from backend.utils.db import get_users_collection
        
        # Extract fields from request
        analysis_id = request.get("analysisId")
        repo_name = request.get("repo")
        title = request.get("title")
        description = request.get("description")
        head = request.get("head")
        base = request.get("base", "main")
        draft = request.get("draft", False)
        user_id_from_request = request.get("userId")
        
        logger.info(f"[CreatePR] Request received - analysisId: {analysis_id}, repo: {repo_name}")
        logger.info(f"[CreatePR] User from request: {user_id_from_request}")
        
        if not all([analysis_id, repo_name, title, description, head]):
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: analysisId, repo, title, description, head"
            )
        
        # Get user ID from analysis document or from request
        repos_col = await get_repos_collection()
        analysis_doc = None
        
        if ObjectId.is_valid(analysis_id):
            analysis_doc = await repos_col.find_one({"_id": ObjectId(analysis_id)})
        
        if not analysis_doc:
            analysis_doc = await repos_col.find_one({"_id": analysis_id})
        
        # Prefer user_id from request, fallback to analysis document
        user_id = user_id_from_request
        if not user_id and analysis_doc:
            user_id = analysis_doc.get("user_id")
            logger.info(f"[CreatePR] Got user_id from analysis doc: {user_id}")
        
        if not user_id:
            logger.error(f"[CreatePR] No user_id found! Analysis doc fields: {list(analysis_doc.keys()) if analysis_doc else 'N/A'}")
            raise HTTPException(status_code=401, detail="User not identified. Please ensure you are logged in.")
        
        # Get user's GitHub access token
        users_col = await get_users_collection()
        logger.info(f"[CreatePR] Looking up user: {user_id}")
        
        # Try multiple ways to find user
        user = None
        if ObjectId.is_valid(user_id):
            user = await users_col.find_one({"_id": ObjectId(user_id)})
        if not user:
            user = await users_col.find_one({"_id": user_id})
        if not user:
            user = await users_col.find_one({"user_id": user_id})
        
        if not user:
            logger.error(f"[CreatePR] User not found with ID: {user_id}")
            raise HTTPException(status_code=404, detail="User profile not found")
        
        logger.info(f"[CreatePR] Found user: {user.get('email', 'N/A')}, has token: {bool(user.get('github_access_token'))}")
        
        if not user.get("github_access_token"):
            logger.error(f"[CreatePR] No GitHub token for user {user_id}. User doc fields: {list(user.keys())}")
            raise HTTPException(
                status_code=401,
                detail="GitHub not connected. Please connect your GitHub account first."
            )
        
        access_token = user["github_access_token"]
        logger.info(f"[CreatePR] Using GitHub token (length: {len(access_token)})")
        
        # Create PR via GitHub API
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        pr_payload = {
            "title": title,
            "body": description,
            "head": head,
            "base": base,
            "draft": draft,
        }
        
        logger.info(f"[CreatePR] PR Payload: {pr_payload}")
        logger.info(f"[CreatePR] Target repo: {repo_name}")
        
        # Validate branches exist before creating PR
        logger.info(f"[CreatePR] Validating branches - checking if '{head}' and '{base}' exist in {repo_name}")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Check if head branch exists
                head_check = await client.get(
                    f"{GITHUB_API_BASE}/repos/{repo_name}/branches/{head}",
                    timeout=5,
                )
                logger.info(f"[CreatePR] Head branch '{head}' check: {head_check.status_code}")
                
                # Check if base branch exists
                base_check = await client.get(
                    f"{GITHUB_API_BASE}/repos/{repo_name}/branches/{base}",
                    timeout=5,
                )
                logger.info(f"[CreatePR] Base branch '{base}' check: {base_check.status_code}")
                
                if head_check.status_code != 200:
                    logger.error(f"[CreatePR] Head branch '{head}' not found")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Head branch '{head}' does not exist in the repository"
                    )
                
                if base_check.status_code != 200:
                    logger.error(f"[CreatePR] Base branch '{base}' not found")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Base branch '{base}' does not exist in the repository"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"[CreatePR] Could not validate branches: {e}")
            # Continue anyway, GitHub will return proper errors
        
        async with httpx.AsyncClient(timeout=30) as client:
            pr_response = await client.post(
                f"{GITHUB_API_BASE}/repos/{repo_name}/pulls",
                json=pr_payload,
                headers=headers,
            )
            
            logger.info(f"[CreatePR] GitHub response status: {pr_response.status_code}")
            
            if pr_response.status_code == 201:
                pr_data = pr_response.json()
                return {
                    "success": True,
                    "pr_number": pr_data.get("number"),
                    "html_url": pr_data.get("html_url"),
                    "pr_url": pr_data.get("html_url"),
                }
            elif pr_response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="GitHub token expired. Please reconnect your GitHub account."
                )
            else:
                try:
                    error_data = pr_response.json()
                    error_msg = error_data.get("message", "Failed to create PR")
                    # GitHub returns detailed validation errors in "errors" array
                    if "errors" in error_data:
                        error_details = ", ".join([str(e) for e in error_data["errors"]])
                        error_msg = f"{error_msg}: {error_details}"
                    logger.error(f"[CreatePR] GitHub PR creation failed: {error_msg}")
                    logger.error(f"[CreatePR] Full GitHub error response: {error_data}")
                except:
                    error_text = pr_response.text
                    logger.error(f"[CreatePR] GitHub error (non-JSON): {error_text}")
                    raise HTTPException(status_code=400, detail=error_text)
                raise HTTPException(status_code=400, detail=error_msg)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PR creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PR creation failed: {str(e)}")


@router.post("/create-pr-safe")
async def create_pull_request_safe(request: SafePRRequest):
    """
    Create a pull request with a NEW branch (safe workflow).

    This is the production-ready workflow that:
    1. Creates a new source branch from the base branch
    2. Commits the documentation changes to the new branch
    3. Opens a PR from source -> base

    This prevents accidentally modifying the base branch.
    """
    try:
        from backend.utils.db import get_users_collection

        logger.info(f"[SafePR] Starting safe PR creation")
        logger.info(f"[SafePR] Repo: {request.repo}, Base: {request.baseBranch}, Source: {request.sourceBranch}")

        # Validate: source and base cannot be the same
        if request.sourceBranch == request.baseBranch:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": PRCreationError.SAME_BRANCH,
                    "message": "Source branch cannot be the same as base branch. Please choose a different branch name."
                }
            )

        # Validate branch name format (no spaces, special chars)
        branch_pattern = re.compile(r'^[a-zA-Z0-9/_.-]+$')
        if not branch_pattern.match(request.sourceBranch):
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "invalid_branch_name",
                    "message": "Branch name contains invalid characters. Use only letters, numbers, /, _, ., and -"
                }
            )

        # Get user's GitHub token
        repos_col = await get_repos_collection()
        analysis_doc = None

        if ObjectId.is_valid(request.analysisId):
            analysis_doc = await repos_col.find_one({"_id": ObjectId(request.analysisId)})
        if not analysis_doc:
            analysis_doc = await repos_col.find_one({"_id": request.analysisId})

        user_id = request.userId
        if not user_id and analysis_doc:
            user_id = analysis_doc.get("user_id")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail={
                    "error_type": "not_authenticated",
                    "message": "User not identified. Please ensure you are logged in."
                }
            )

        users_col = await get_users_collection()
        user = None
        if ObjectId.is_valid(user_id):
            user = await users_col.find_one({"_id": ObjectId(user_id)})
        if not user:
            user = await users_col.find_one({"_id": user_id})
        if not user:
            user = await users_col.find_one({"user_id": user_id})

        if not user or not user.get("github_access_token"):
            raise HTTPException(
                status_code=401,
                detail={
                    "error_type": PRCreationError.TOKEN_EXPIRED,
                    "message": "GitHub not connected. Please connect your GitHub account first."
                }
            )

        access_token = user["github_access_token"]
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            # Step 0: Pre-flight check - verify token and repo access
            logger.info(f"[SafePR] Pre-flight check: verifying GitHub token and repo access")
            
            # Check if token is valid by getting authenticated user
            user_check = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers=headers,
            )
            
            if user_check.status_code == 401:
                logger.error(f"[SafePR] GitHub token is invalid or expired")
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error_type": PRCreationError.TOKEN_EXPIRED,
                        "message": "GitHub token is invalid or expired. Please reconnect your GitHub account."
                    }
                )
            elif user_check.status_code != 200:
                logger.error(f"[SafePR] Could not verify GitHub token: {user_check.status_code}")
                raise HTTPException(
                    status_code=500,
                    detail={"error_type": "token_check_failed", "message": "Could not verify GitHub token"}
                )
            
            authenticated_user = user_check.json().get("login")
            logger.info(f"[SafePR] Token is valid, authenticated as: {authenticated_user}")
            
            # Check if we can access the repository
            logger.info(f"[SafePR] Checking access to repository: {request.repo}")
            repo_check = await client.get(
                f"{GITHUB_API_BASE}/repos/{request.repo}",
                headers=headers,
            )
            
            if repo_check.status_code == 404:
                logger.error(f"[SafePR] Repository not found or no access: {request.repo}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error_type": PRCreationError.REPO_NOT_FOUND,
                        "message": f"Repository '{request.repo}' not found or you don't have access. Check the repository name and your token permissions."
                    }
                )
            elif repo_check.status_code != 200:
                logger.error(f"[SafePR] Could not access repository: {repo_check.status_code}")
                raise HTTPException(
                    status_code=500,
                    detail={"error_type": "repo_check_failed", "message": "Could not access repository"}
                )
            
            repo_data = repo_check.json()
            logger.info(f"[SafePR] Repository access confirmed. Push access: {repo_data.get('permissions', {}).get('push', False)}")
            
            # Verify we have push access
            if not repo_data.get('permissions', {}).get('push', False):
                logger.error(f"[SafePR] No push access to repository")
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error_type": PRCreationError.NO_WRITE_ACCESS,
                        "message": "You don't have write/push access to this repository. You may need to fork the repository or ask for collaborator access."
                    }
                )

            # Step 1: Get the SHA of the base branch
            logger.info(f"[SafePR] Getting SHA of base branch '{request.baseBranch}' for repo '{request.repo}'")
            base_ref_response = await client.get(
                f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs/heads/{request.baseBranch}",
                headers=headers,
            )

            if base_ref_response.status_code == 404:
                logger.error(f"[SafePR] Base branch not found: {base_ref_response.text}")
                # Try to get available branches to help user
                available_branches = []
                try:
                    branches_list_response = await client.get(
                        f"{GITHUB_API_BASE}/repos/{request.repo}/branches?per_page=20",
                        headers=headers,
                        timeout=5,
                    )
                    if branches_list_response.status_code == 200:
                        branches_data = branches_list_response.json()
                        available_branches = [b["name"] for b in branches_data]
                        logger.info(f"[SafePR] Available branches: {available_branches}")
                except Exception as e:
                    logger.warning(f"[SafePR] Could not fetch available branches: {e}")
                
                detail = {
                    "error_type": "base_branch_not_found",
                    "message": f"Base branch '{request.baseBranch}' not found in {request.repo}. Please select a valid base branch.",
                }
                if available_branches:
                    detail["available_branches"] = available_branches
                    detail["message"] = f"Base branch '{request.baseBranch}' not found. Available branches: {', '.join(available_branches[:5])}"
                
                raise HTTPException(
                    status_code=400,
                    detail=detail
                )
            elif base_ref_response.status_code != 200:
                error_data = base_ref_response.json() if base_ref_response.text else {}
                error_type, error_msg = classify_github_error(base_ref_response.status_code, error_data)
                logger.error(f"[SafePR] Failed to get base branch: {error_data}")
                raise HTTPException(
                    status_code=base_ref_response.status_code,
                    detail={"error_type": error_type, "message": error_msg}
                )

            try:
                response_json = base_ref_response.json()
                base_sha = response_json.get("object", {}).get("sha")
                if not base_sha:
                    logger.error(f"[SafePR] Invalid response format - no SHA found: {response_json}")
                    raise HTTPException(
                        status_code=500,
                        detail={"error_type": "invalid_response", "message": "GitHub API returned unexpected response format"}
                    )
            except Exception as e:
                logger.error(f"[SafePR] Failed to parse base branch response: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={"error_type": "parse_error", "message": f"Failed to parse GitHub response: {str(e)}"}
                )
            
            logger.info(f"[SafePR] Base branch SHA: {base_sha}")

            # Step 2: Validate the SHA actually exists by checking the commit
            logger.info(f"[SafePR] Validating SHA exists: {base_sha}")
            commit_check = await client.get(
                f"{GITHUB_API_BASE}/repos/{request.repo}/git/commits/{base_sha}",
                headers=headers,
            )
            
            if commit_check.status_code == 404:
                logger.error(f"[SafePR] SHA not found in repository: {base_sha}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error_type": "commit_not_found",
                        "message": f"Commit SHA from base branch not found in repository. The repository may have been reset or force-pushed."
                    }
                )
            elif commit_check.status_code != 200:
                logger.warning(f"[SafePR] Could not validate SHA (continuing anyway): {commit_check.status_code}")

            # Step 3: Check if source branch already exists
            logger.info(f"[SafePR] Checking if source branch '{request.sourceBranch}' exists")
            source_check = await client.get(
                f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs/heads/{request.sourceBranch}",
                headers=headers,
            )

            if source_check.status_code == 200:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error_type": PRCreationError.BRANCH_EXISTS,
                        "message": f"Branch '{request.sourceBranch}' already exists. Please choose a different branch name or use a unique identifier."
                    }
                )

            # Step 4: Create the new source branch from base
            logger.info(f"[SafePR] Creating source branch '{request.sourceBranch}' from SHA {base_sha}")
            
            # Try method 1: Using git refs API
            create_ref_response = await client.post(
                f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs",
                headers=headers,
                json={
                    "ref": f"refs/heads/{request.sourceBranch}",
                    "sha": base_sha,
                }
            )

            if create_ref_response.status_code == 404:
                # 404 might mean permission denied or endpoint issue
                # Try fallback: create branch via empty commit
                logger.warning(f"[SafePR] Git refs endpoint returned 404, trying alternative method...")
                
                # Get tree SHA from base commit
                base_commit = await client.get(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/commits/{base_sha}",
                    headers=headers,
                )
                
                if base_commit.status_code != 200:
                    logger.error(f"[SafePR] Could not fetch base commit: {base_commit.text}")
                    raise HTTPException(
                        status_code=400,
                        detail={"error_type": "commit_fetch_failed", "message": "Could not fetch base commit information"}
                    )
                
                tree_sha = base_commit.json()["tree"]["sha"]
                logger.info(f"[SafePR] Using tree SHA from base commit: {tree_sha}")
                
                # Create a new commit with the same tree
                new_commit_response = await client.post(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/commits",
                    headers=headers,
                    json={
                        "message": request.commitMessage,
                        "tree": tree_sha,
                        "parents": [base_sha]
                    }
                )
                
                if new_commit_response.status_code != 201:
                    logger.error(f"[SafePR] Failed to create commit: {new_commit_response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail={"error_type": "commit_creation_failed", "message": "Failed to create new commit"}
                    )
                
                new_commit_sha = new_commit_response.json()["sha"]
                logger.info(f"[SafePR] Created new commit: {new_commit_sha}")
                
                # Now create ref pointing to new commit
                create_ref_response = await client.post(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs",
                    headers=headers,
                    json={
                        "ref": f"refs/heads/{request.sourceBranch}",
                        "sha": new_commit_sha,
                    }
                )
            
            if create_ref_response.status_code not in [200, 201]:
                error_data = create_ref_response.json() if create_ref_response.text else {}
                error_type, error_msg = classify_github_error(create_ref_response.status_code, error_data)
                logger.error(f"[SafePR] Failed to create branch with SHA {base_sha}: {error_data}")
                logger.error(f"[SafePR] Response status: {create_ref_response.status_code}, headers: {dict(create_ref_response.headers)}")
                
                # Give user a more helpful error message
                if create_ref_response.status_code == 404:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error_type": "no_write_access",
                            "message": f"No write access to repository or branch protection enabled. Check your GitHub token permissions and repository settings."
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=create_ref_response.status_code,
                        detail={"error_type": error_type, "message": error_msg}
                    )

            logger.info(f"[SafePR] Successfully created source branch '{request.sourceBranch}'")

            # Step 4: Commit changes to the new branch
            # If no files provided, create a placeholder commit with documentation info
            files_to_commit = list(request.files) if request.files else []

            # If no files are provided, we need to create at least one change
            # otherwise GitHub will reject the PR with "no commits between branches"
            if not files_to_commit:
                logger.info(f"[SafePR] No files provided, creating placeholder documentation file")
                # Create a placeholder documentation file
                placeholder_content = f"""# Documentation Update

This branch contains AI-generated documentation improvements.

## Analysis ID
`{request.analysisId}`

## Generated by
CodeIQ - AI-powered code documentation

## PR Details
- **Title**: {request.title}
- **Branch**: `{request.sourceBranch}`
- **Base**: `{request.baseBranch}`

---
*This file was auto-generated by CodeIQ.*
"""
                files_to_commit = [FileChange(
                    path=".codeiq/DOCUMENTATION_UPDATE.md",
                    content=placeholder_content,
                    action="create"
                )]

            logger.info(f"[SafePR] Committing {len(files_to_commit)} file(s) to '{request.sourceBranch}'")

            # Get the current tree
            commit_response = await client.get(
                f"{GITHUB_API_BASE}/repos/{request.repo}/git/commits/{base_sha}",
                headers=headers,
            )
            current_tree_sha = commit_response.json()["tree"]["sha"]

            # Create blobs for each file
            tree_items = []
            for file_change in files_to_commit:
                # Create blob
                blob_response = await client.post(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/blobs",
                    headers=headers,
                    json={
                        "content": file_change.content,
                        "encoding": "utf-8"
                    }
                )

                if blob_response.status_code != 201:
                    logger.error(f"[SafePR] Failed to create blob for {file_change.path}: {blob_response.text}")
                    continue

                blob_sha = blob_response.json()["sha"]
                tree_items.append({
                    "path": file_change.path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha
                })

            if not tree_items:
                # Clean up the branch we created
                await client.delete(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs/heads/{request.sourceBranch}",
                    headers=headers,
                )
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error_type": "no_changes",
                        "message": "No files could be committed. Please ensure there are documentation changes to commit."
                    }
                )

            # Create new tree
            tree_response = await client.post(
                f"{GITHUB_API_BASE}/repos/{request.repo}/git/trees",
                headers=headers,
                json={
                    "base_tree": current_tree_sha,
                    "tree": tree_items
                }
            )

            if tree_response.status_code != 201:
                logger.error(f"[SafePR] Failed to create tree: {tree_response.text}")
                # Clean up
                await client.delete(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs/heads/{request.sourceBranch}",
                    headers=headers,
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error_type": "commit_failed",
                        "message": "Failed to create commit tree. Please try again."
                    }
                )

            new_tree_sha = tree_response.json()["sha"]

            # Create commit
            commit_create_response = await client.post(
                f"{GITHUB_API_BASE}/repos/{request.repo}/git/commits",
                headers=headers,
                json={
                    "message": request.commitMessage,
                    "tree": new_tree_sha,
                    "parents": [base_sha]
                }
            )

            if commit_create_response.status_code != 201:
                logger.error(f"[SafePR] Failed to create commit: {commit_create_response.text}")
                # Clean up
                await client.delete(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs/heads/{request.sourceBranch}",
                    headers=headers,
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error_type": "commit_failed",
                        "message": "Failed to create commit. Please try again."
                    }
                )

            new_commit_sha = commit_create_response.json()["sha"]

            # Update branch reference
            update_ref_response = await client.patch(
                f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs/heads/{request.sourceBranch}",
                headers=headers,
                json={"sha": new_commit_sha, "force": True}
            )

            if update_ref_response.status_code != 200:
                logger.error(f"[SafePR] Failed to update ref: {update_ref_response.text}")
                # Clean up
                await client.delete(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs/heads/{request.sourceBranch}",
                    headers=headers,
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error_type": "commit_failed",
                        "message": "Failed to update branch reference. Please try again."
                    }
                )

            logger.info(f"[SafePR] Successfully committed changes to '{request.sourceBranch}'")

            # Step 5: Create the Pull Request
            logger.info(f"[SafePR] Creating PR: {request.sourceBranch} -> {request.baseBranch}")
            pr_payload = {
                "title": request.title,
                "body": request.description,
                "head": request.sourceBranch,
                "base": request.baseBranch,
                "draft": request.draft,
            }

            pr_response = await client.post(
                f"{GITHUB_API_BASE}/repos/{request.repo}/pulls",
                headers=headers,
                json=pr_payload,
            )

            if pr_response.status_code == 201:
                pr_data = pr_response.json()
                logger.info(f"[SafePR] PR created successfully: {pr_data.get('html_url')}")

                # Update analysis doc with PR info
                if analysis_doc:
                    await repos_col.update_one(
                        {"_id": analysis_doc["_id"]},
                        {
                            "$set": {
                                "github_pr_number": pr_data.get("number"),
                                "github_pr_url": pr_data.get("html_url"),
                                "github_pr_branch": request.sourceBranch,
                                "github_pr_created_at": datetime.utcnow().isoformat(),
                            }
                        }
                    )

                return {
                    "success": True,
                    "pr_number": pr_data.get("number"),
                    "html_url": pr_data.get("html_url"),
                    "pr_url": pr_data.get("html_url"),
                    "branch": request.sourceBranch,
                    "state": pr_data.get("state"),
                }
            else:
                error_data = pr_response.json() if pr_response.text else {}
                error_type, error_msg = classify_github_error(pr_response.status_code, error_data)
                logger.error(f"[SafePR] PR creation failed: {error_data}")

                # Clean up: delete the branch we just created
                logger.info(f"[SafePR] Cleaning up - deleting branch '{request.sourceBranch}'")
                await client.delete(
                    f"{GITHUB_API_BASE}/repos/{request.repo}/git/refs/heads/{request.sourceBranch}",
                    headers=headers,
                )

                raise HTTPException(
                    status_code=pr_response.status_code,
                    detail={"error_type": error_type, "message": error_msg}
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SafePR] PR creation failed unexpectedly: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": PRCreationError.UNKNOWN,
                "message": f"An unexpected error occurred: {str(e)}"
            }
        )


@router.get("/{analysisId}/export")
async def export_documentation(analysisId: str):
    """
    Export documentation as a downloadable ZIP file.

    Returns a ZIP archive containing all generated documentation files.
    """
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    logger.info(f"[Export] Exporting documentation for analysis: {analysisId}")

    repos_col = await get_repos_collection()

    # Find analysis document
    analysis_doc = None
    if ObjectId.is_valid(analysisId):
        analysis_doc = await repos_col.find_one({"_id": ObjectId(analysisId)})
    if not analysis_doc:
        analysis_doc = await repos_col.find_one({"_id": analysisId})

    if not analysis_doc:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Get documentation from the analysis
    documentation = analysis_doc.get("documentation", [])
    repo_name = analysis_doc.get("repo_name", "documentation")

    # Also try to get docstrings from stats if documentation array is empty
    if not documentation:
        stats = analysis_doc.get("stats", {})
        if stats.get("docstrings"):
            documentation = stats.get("docstrings", [])

    if not documentation:
        logger.warning(f"[Export] No documentation found for analysis {analysisId}")
        raise HTTPException(status_code=400, detail="No documentation available for export")

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for idx, doc in enumerate(documentation):
            if isinstance(doc, dict):
                file_name = doc.get("file_name", doc.get("path", f"doc_{idx}"))
                content = doc.get("content", doc.get("docstring", ""))
            else:
                file_name = f"doc_{idx}"
                content = str(doc)

            # Ensure .md extension
            if not file_name.endswith('.md'):
                file_name = f"{file_name}.md"

            # Clean path
            file_name = file_name.replace("\\", "/").lstrip("/")

            if content:
                zip_file.writestr(f"docs/{file_name}", content)

    zip_buffer.seek(0)

    # Clean repo name for filename
    safe_repo_name = repo_name.replace("/", "-").replace("\\", "-")

    logger.info(f"[Export] Created ZIP with {len(documentation)} documentation files")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_repo_name}-documentation.zip"'
        }
    )


@router.get("/{analysisId}/github-status")
async def check_github_connection(analysisId: str):
    """
    Check if GitHub is connected for the user associated with this analysis.

    Returns:
    {
        "connected": bool,
        "has_token": bool,
        "message": str
    }
    """
    try:
        from backend.utils.db import get_users_collection, get_database
        
        repos_col = await get_repos_collection()
        
        # Get analysis document - try multiple collections
        analysis_doc = None
        if ObjectId.is_valid(analysisId):
            analysis_doc = await repos_col.find_one({"_id": ObjectId(analysisId)})
        
        if not analysis_doc:
            analysis_doc = await repos_col.find_one({"_id": analysisId})
        
        # Try analysis collection as well
        if not analysis_doc:
            try:
                db = await get_database()
                analysis_col = db.get_collection("analyses")
                if ObjectId.is_valid(analysisId):
                    analysis_doc = await analysis_col.find_one({"_id": ObjectId(analysisId)})
                if not analysis_doc:
                    analysis_doc = await analysis_col.find_one({"_id": analysisId})
            except Exception as e:
                logger.warning(f"Could not check analyses collection: {e}")
        
        if not analysis_doc:
            logger.warning(f"Analysis document not found for ID: {analysisId}")
            return {
                "connected": False,
                "has_token": False,
                "message": "Analysis not found"
            }
        
        logger.info(f"Found analysis doc fields: {list(analysis_doc.keys())}")
        
        user_id = analysis_doc.get("user_id")
        if not user_id:
            logger.warning(f"No user_id in analysis doc {analysisId}")
            # Try to get user from request context if available
            return {
                "connected": False,
                "has_token": False,
                "message": "Analysis not associated with user"
            }
        
        # Get user and check for GitHub token
        users_col = await get_users_collection()
        user = None
        if isinstance(user_id, str) and ObjectId.is_valid(user_id):
            user = await users_col.find_one({"_id": ObjectId(user_id)})
        if not user:
            user = await users_col.find_one({"_id": user_id})
        if not user and isinstance(user_id, str):
            user = await users_col.find_one({"user_id": user_id})
        
        if not user:
            logger.warning(f"User not found for ID: {user_id}")
            return {
                "connected": False,
                "has_token": False,
                "message": "User not found"
            }
        
        has_token = bool(user.get("github_access_token"))
        logger.info(f"GitHub connection check for user {user_id}: has_token={has_token}")
        
        return {
            "connected": has_token,
            "has_token": has_token,
            "message": "GitHub is connected" if has_token else "GitHub is not connected. Please connect your GitHub account to create pull requests."
        }
    
    except Exception as e:
        logger.error(f"Failed to check GitHub connection: {e}", exc_info=True)
        return {
            "connected": False,
            "has_token": False,
            "message": "Error checking GitHub connection"
        }
