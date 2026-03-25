"""
GitHub integration API routes.

Handles GitHub OAuth, repository fetching, app installation, and PR creation.
"""

import hmac
import hashlib
import json
import jwt
import time
import asyncio
import subprocess
import os
import shutil
from urllib.parse import urlencode
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

import httpx
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel

from backend.models.github import (
    GitHubUserProfileResponse,
    AuthorizeGitHubRequest,
    CreatePRRequest,
    InstallationWebhookPayload,
)
from backend.models.repository import RepositoryDoc
from backend.utils.db import get_users_collection, get_repos_collection
from backend.utils.logger import get_logger
from backend.utils.paths import DATA_ROOT

router = APIRouter(prefix="/api/github", tags=["github"])
logger = get_logger(__name__)

# ── Configuration ────────────────────────────────────────────────────

GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_ACCESS_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://localhost:3000/dashboard")
GITHUB_APP_SLUG = os.getenv("GITHUB_APP_SLUG", "codeiq")

# Load from environment
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
GITHUB_APP_WEBHOOK_SECRET = os.getenv("GITHUB_APP_WEBHOOK_SECRET", "")

def _generate_app_jwt() -> str:
    """Generate short-lived JWT for GitHub App API calls."""
    if not GITHUB_APP_PRIVATE_KEY or not GITHUB_APP_ID:
        raise ValueError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY must be set")

    now = int(time.time())
    payload = {
        "iss": GITHUB_APP_ID,
        "iat": now,
        "exp": now + 600,
    }
    return jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm="RS256")

async def _resolve_app_slug() -> str:
    """Resolve the GitHub App slug from GitHub API, fallback to env-configured slug."""
    try:
        app_jwt = _generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "CodeIQ-GitHub-Integrations",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{GITHUB_API_BASE}/app", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            slug = data.get("slug")
            if slug:
                return slug
    except Exception as e:
        logger.warning(f"Could not resolve GitHub app slug dynamically, using fallback '{GITHUB_APP_SLUG}': {e}")

    return GITHUB_APP_SLUG
CLONE_DIR = DATA_ROOT / "input" / "repositories"
CLONE_DIR.mkdir(parents=True, exist_ok=True)

# ── Helper Functions ────────────────────────────────────────────────

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature."""
    if not GITHUB_APP_WEBHOOK_SECRET:
        logger.warning("GITHUB_APP_WEBHOOK_SECRET not set - webhook verification skipped")
        return True

    expected = "sha256=" + hmac.new(
        GITHUB_APP_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


def generate_app_token(installation_id: int) -> str:
    """
    Generate a GitHub App installation access token.
    
    Uses the private key and app ID to create a JWT, then exchanges it
    for an installation access token.
    """
    if not GITHUB_APP_PRIVATE_KEY or not GITHUB_APP_ID:
        raise ValueError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY must be set")

    # Generate JWT (valid for 10 minutes)
    now = int(time.time())
    payload = {
        "iss": GITHUB_APP_ID,
        "iat": now,
        "exp": now + 600,
    }
    
    jwt_token = jwt.encode(
        payload,
        GITHUB_APP_PRIVATE_KEY,
        algorithm="RS256"
    )

    # Exchange JWT for installation token
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    
    try:
        import httpx
        response = httpx.post(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["token"]
    except Exception as e:
        logger.error(f"Failed to generate app token: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate GitHub token")


def _user_filters(user_id: str) -> list[dict]:
    """Build robust user filters that work for both string and ObjectId _id values."""
    filters = [{"_id": user_id}, {"user_id": user_id}, {"id": user_id}]
    if ObjectId.is_valid(user_id):
        filters.append({"_id": ObjectId(user_id)})
    return filters


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/authorize")
async def authorize_github(request: AuthorizeGitHubRequest, user_id: str = Header(None)):
    """
    GitHub OAuth callback - exchange code for access token.
    
    Query params: code, state
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    if not request.code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        # Exchange code for access token
        logger.info(f"[OAuth] Exchanging code for token")
        logger.info(f"[OAuth] Code: {request.code[:20]}..." if len(request.code) > 20 else f"[OAuth] Code: {request.code}")
        logger.info(f"[OAuth] Client ID: {GITHUB_CLIENT_ID[:10]}...")
        logger.info(f"[OAuth] Client Secret configured: {bool(GITHUB_CLIENT_SECRET)}")
        
        async with httpx.AsyncClient(follow_redirects=False) as client:
            try:
                # Prepare the request parameters
                payload = {
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": request.code,
                    "redirect_uri": GITHUB_OAUTH_REDIRECT_URI,
                }
                logger.info(f"[OAuth] Sending request to: {GITHUB_OAUTH_ACCESS_TOKEN}")
                logger.info(f"[OAuth] Redirect URI: {GITHUB_OAUTH_REDIRECT_URI}")
                
                response = await client.post(
                    GITHUB_OAUTH_ACCESS_TOKEN,
                    data=payload,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "CodeIQ-GitHub-Integrations",
                    },
                    timeout=15,
                )
                
                logger.info(f"[OAuth] Token response status: {response.status_code}")
                logger.info(f"[OAuth] Response content-type: {response.headers.get('content-type')}")
                
                if response.status_code not in [200, 201]:
                    response_text = response.text[:500]
                    logger.error(f"[OAuth] Token exchange failed with status {response.status_code}")
                    logger.error(f"[OAuth] Response body: {response_text}")
                    # Try to parse error details
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error_description") or error_data.get("error") or response_text
                    except:
                        error_msg = response_text
                    raise HTTPException(status_code=400, detail=f"GitHub auth failed: {error_msg}")
                
                token_data = response.json()
                
                if "error" in token_data:
                    error_msg = token_data.get("error_description", token_data.get("error", "Unknown error"))
                    logger.error(f"[OAuth] GitHub error: {error_msg}")
                    raise HTTPException(status_code=400, detail=f"GitHub error: {error_msg}")
                
                if "access_token" not in token_data:
                    logger.error(f"[OAuth] No access token in response: {token_data}")
                    raise HTTPException(status_code=400, detail="No access token in GitHub response")
                
                access_token = token_data["access_token"]
                logger.info(f"[OAuth] Successfully obtained access token")
            except httpx.HTTPError as http_err:
                logger.error(f"[OAuth] HTTP error during token exchange: {http_err}")
                raise HTTPException(status_code=500, detail=f"HTTP error: {str(http_err)}")

            # Fetch GitHub user profile
            logger.info(f"[OAuth] Fetching user profile...")
            headers = {
                "Authorization": f"token {access_token}",
                "User-Agent": "CodeIQ-GitHub-Integrations",
            }
            
            user_response = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers=headers,
                timeout=10,
            )
            user_response.raise_for_status()
            github_user = user_response.json()
            logger.info(f"[OAuth] User profile fetched: {github_user.get('login')}")

        # Save to database
        users_col = await get_users_collection()
        result = await users_col.update_one(
            {"$or": _user_filters(user_id)},
            {
                "$set": {
                    "github_id": github_user["id"],
                    "github_login": github_user["login"],
                    "github_avatar_url": github_user.get("avatar_url"),
                    "github_access_token": access_token,
                    "github_token_expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                    "github_connected_at": datetime.utcnow().isoformat(),
                }
            },
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Authenticated user not found for GitHub connection")
        logger.info(f"[OAuth] User record updated: {result.modified_count} documents modified")

        return {
            "success": True,
            "github_login": github_user["login"],
            "github_id": github_user["id"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[OAuth] Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Authorization failed: {str(e)}")


@router.get("/repositories")
async def get_github_repositories(user_id: str = Header(None)):
    """
    Fetch user's GitHub repositories.
    
    Requires user to be connected via GitHub OAuth.
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    try:
        users_col = await get_users_collection()
        user = await users_col.find_one({"$or": _user_filters(user_id)})
        
        if not user or not user.get("github_access_token"):
            return {
                "repositories": [],
                "total": 0,
                "profile": None,
                "connected": False,
            }

        access_token = user["github_access_token"]
        headers = {"Authorization": f"token {access_token}"}

        async with httpx.AsyncClient() as client:
            # Fetch user repositories
            repos_response = await client.get(
                f"{GITHUB_API_BASE}/user/repos?per_page=100&type=owner",
                headers=headers,
                timeout=10,
            )
            if repos_response.status_code in (401, 403):
                # Token expired/revoked or insufficient scope.
                await users_col.update_one(
                    {"$or": _user_filters(user_id)},
                    {"$unset": {"github_access_token": "", "github_token_expires_at": ""}},
                )
                raise HTTPException(status_code=401, detail="GitHub token expired or invalid. Please reconnect GitHub.")
            try:
                repos_response.raise_for_status()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (401, 403):
                    raise HTTPException(status_code=401, detail="GitHub token expired or unauthorized. Please reconnect GitHub.")
                raise
            repos = repos_response.json()

            semaphore = asyncio.Semaphore(10)

            async def enrich_repo(repo: dict) -> dict:
                app_installed = False
                installation_id = None

                try:
                    app_jwt = _generate_app_jwt()
                    app_headers = {
                        "Authorization": f"Bearer {app_jwt}",
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "CodeIQ-GitHub-Integrations",
                    }
                    async with semaphore:
                        inst_response = await client.get(
                            f"{GITHUB_API_BASE}/repos/{repo['full_name']}/installation",
                            headers=app_headers,
                            timeout=5,
                        )
                    if inst_response.status_code == 200:
                        inst_data = inst_response.json()
                        installation_id = inst_data.get("id")
                        app_installed = True
                except Exception as e:
                    logger.debug(f"Could not check app installation for {repo['full_name']}: {e}")

                return {
                    "github_repo_id": repo["id"],
                    "owner": repo["owner"]["login"],
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description"),
                    "url": repo["html_url"],
                    "clone_url": repo["clone_url"],
                    "private": repo["private"],
                    "language": repo.get("language"),
                    "stars": repo["stargazers_count"],
                    "app_installed": app_installed,
                    "installation_id": installation_id,
                }

            formatted_repos = await asyncio.gather(*(enrich_repo(repo) for repo in repos))

        return {
            "repositories": formatted_repos,
            "total": len(formatted_repos),
            "profile": {
                "github_id": user.get("github_id"),
                "github_login": user.get("github_login"),
            } if user.get("github_id") and user.get("github_login") else None,
            "connected": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch GitHub repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect")
async def disconnect_github(user_id: str = Header(None)):
    """Disconnect GitHub account by removing stored OAuth and app installation metadata."""
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    users_col = await get_users_collection()
    user = await users_col.find_one({"$or": _user_filters(user_id)})

    # Revoke token/grant so the next connect flow requires authorization again.
    access_token = user.get("github_access_token") if user else None
    if access_token and GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET:
        try:
            auth = (GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET)
            async with httpx.AsyncClient(timeout=10) as client:
                await client.delete(
                    f"https://api.github.com/applications/{GITHUB_CLIENT_ID}/grant",
                    auth=auth,
                    headers={"Accept": "application/vnd.github+json"},
                    json={"access_token": access_token},
                )
                await client.delete(
                    f"https://api.github.com/applications/{GITHUB_CLIENT_ID}/token",
                    auth=auth,
                    headers={"Accept": "application/vnd.github+json"},
                    json={"access_token": access_token},
                )
        except Exception as e:
            logger.warning(f"Failed to revoke GitHub OAuth token/grant during disconnect: {e}")

    result = await users_col.update_one(
        {"$or": _user_filters(user_id)},
        {
            "$unset": {
                "github_id": "",
                "github_login": "",
                "github_avatar_url": "",
                "github_access_token": "",
                "github_token_expires_at": "",
                "github_connected_at": "",
                "github_app": "",
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Authenticated user not found")

    return {"success": True, "connected": False}


@router.post("/app/install-url")
async def get_app_install_url(request: dict, user_id: str = Header(None)):
    """
    Get GitHub App installation URL for a specific repository.
    
    Returns the URL to install CodeIQ GitHub App for the user.
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    if not GITHUB_APP_ID:
        raise HTTPException(status_code=500, detail="GitHub App not configured")

    repo_id = request.get("repository_id")
    query: dict = {"state": user_id}

    # GitHub expects repeated repository_ids[] params for pre-selection hints.
    if repo_id is not None:
        try:
            query["repository_ids[]"] = [int(repo_id)]
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid repository_id")

    app_slug = await _resolve_app_slug()
    install_url = f"https://github.com/apps/{app_slug}/installations/new?{urlencode(query, doseq=True)}"

    return {"install_url": install_url}


@router.post("/webhook/installation")
async def handle_installation_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
):
    """
    GitHub App installation webhook.
    
    Handles app installation/uninstallation events.
    """
    if not x_github_event or not x_hub_signature_256:
        raise HTTPException(status_code=400, detail="Missing headers")

    # Read and verify request body
    payload = await request.body()
    
    if not verify_webhook_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = json.loads(payload)
        action = data.get("action")
        installation = data.get("installation", {})
        
        installation_id = installation.get("id")
        repositories = data.get("repositories", [])

        logger.info(f"GitHub App {action}: installation_id={installation_id}")

        # Store installation info in database
        apps_col = await get_users_collection()
        
        for repo in repositories:
            await apps_col.update_one(
                {"_id": installation.get("owner", {}).get("login")},
                {
                    "$set": {
                        f"github_app.{repo['id']}": {
                            "name": repo["name"],
                            "full_name": repo["full_name"],
                            "installation_id": installation_id,
                            "installed_at": datetime.utcnow().isoformat(),
                        }
                    }
                },
            )

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def github_health_check():
    """
    Diagnostic endpoint to check GitHub OAuth configuration.
    """
    return {
        "status": "ok",
        "github_client_id_set": bool(GITHUB_CLIENT_ID),
        "github_client_secret_set": bool(GITHUB_CLIENT_SECRET),
        "github_app_id_set": bool(GITHUB_APP_ID),
        "github_app_private_key_set": bool(GITHUB_APP_PRIVATE_KEY),
        "github_webhook_secret_set": bool(GITHUB_APP_WEBHOOK_SECRET),
    }


@router.post("/pr/create")
async def create_docstring_pr(
    request: CreatePRRequest,
    user_id: str = Header(None),
):
    """
    Create a pull request with generated docstrings.
    
    This workflow:
    1. Gets generated docs from the CodeIQ pipeline
    2. Clones the repo with GitHub App permissions
    3. Creates a feature branch
    4. Commits the documentation
    5. Opens a PR
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    try:
        # Get installation token
        app_token = generate_app_token(request.installation_id)
        
        # Fetch the CodeIQ repo to get generated docs
        repos_col = await get_repos_collection()
        repo = await repos_col.find_one({"_id": request.repo_id})
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        if not repo.get("documentation"):
            raise HTTPException(status_code=400, detail="No documentation generated yet")

        # Clone using GitHub App token
        repo_path = CLONE_DIR / f"{request.github_repo_full_name.replace('/', '_')}_pr"
        
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        clone_url = f"https://x-access-token:{app_token}@github.com/{request.github_repo_full_name}.git"
        
        subprocess.run(
            ["git", "clone", clone_url, str(repo_path)],
            check=True,
            capture_output=True,
        )

        # Configure git
        subprocess.run(
            ["git", "config", "user.name", "CodeIQ Bot"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "bot@codeiq.ai"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create feature branch
        subprocess.run(
            ["git", "checkout", "-b", request.commit_message[:50]],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Write documentation files
        docs_dir = repo_path / "CODEIQ_DOCS"
        docs_dir.mkdir(exist_ok=True)
        
        for doc in repo.get("documentation", []):
            file_path = docs_dir / f"{doc.get('file_name', 'doc')}.md"
            file_path.write_text(doc.get("content", ""), encoding="utf-8")

        # Commit
        subprocess.run(
            ["git", "add", "."],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", request.commit_message],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Push
        subprocess.run(
            ["git", "push", "-u", "origin", request.commit_message[:50]],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create PR via GitHub API
        headers = {
            "Authorization": f"token {app_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        pr_data = {
            "title": request.pr_title,
            "body": request.pr_body,
            "head": request.commit_message[:50],
            "base": "main",  # or detect default branch
        }

        async with httpx.AsyncClient() as client:
            pr_response = await client.post(
                f"{GITHUB_API_BASE}/repos/{request.github_repo_full_name}/pulls",
                json=pr_data,
                headers=headers,
                timeout=30,
            )
            pr_response.raise_for_status()
            pr = pr_response.json()

        # Update CodeIQ repo with PR info
        await repos_col.update_one(
            {"_id": request.repo_id},
            {
                "$set": {
                    "github_pr_number": pr["number"],
                    "github_pr_url": pr["html_url"],
                    "github_pr_created_at": datetime.utcnow().isoformat(),
                }
            },
        )

        return {
            "success": True,
            "pr_number": pr["number"],
            "pr_url": pr["html_url"],
            "pr_title": pr["title"],
        }

    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")
        raise HTTPException(status_code=500, detail="Git operation failed")
    except Exception as e:
        logger.error(f"PR creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
