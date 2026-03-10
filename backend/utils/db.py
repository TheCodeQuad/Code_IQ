"""
MongoDB async connection for FastAPI backend.

Uses motor (async MongoDB driver) so all DB calls are non-blocking.
Connection string defaults to the same MongoDB used by the Next.js frontend.
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv

# Load .env from backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/codeiq")

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    """Get or create the singleton Motor client."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URI)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """Get the codeiq database handle."""
    global _db
    if _db is None:
        client = get_client()
        # Extract DB name from URI, fallback to 'codeiq'
        db_name = MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "codeiq"
        _db = client[db_name]
    return _db


async def get_repos_collection():
    """Shortcut: return the repositories collection."""
    db = get_database()
    return db["repositories"]


async def get_users_collection():
    """Shortcut: return the users collection."""
    db = get_database()
    return db["users"]


async def close_connection():
    """Close the MongoDB connection (call on app shutdown)."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None


async def ping() -> bool:
    """Check if MongoDB is reachable."""
    try:
        client = get_client()
        await client.admin.command("ping")
        return True
    except Exception:
        return False


# ── Pipeline status helpers ──────────────────────────────────────────

async def update_repo_status(
    repo_id: str,
    *,
    status: Optional[str] = None,
    current_agent: Optional[str] = None,
    progress_percent: Optional[int] = None,
    error_message: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Update pipeline-related fields on a repository document.
    Only sets the fields that are explicitly provided.
    """
    collection = await get_repos_collection()
    update: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
    if status is not None:
        update["status"] = status
    if current_agent is not None:
        update["current_agent"] = current_agent
    if progress_percent is not None:
        update["progress_percent"] = progress_percent
    if error_message is not None:
        update["error_message"] = error_message
    if extra_fields:
        update.update(extra_fields)
    await collection.update_one(
        {"_id": ObjectId(repo_id)},
        {"$set": update},
    )


async def update_agent_log(
    repo_id: str,
    agent_name: str,
    *,
    agent_status: str,
    message: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
) -> None:
    """
    Update a specific agent entry inside the agent_logs array.
    Uses MongoDB positional operator $ to target the matching element.
    """
    collection = await get_repos_collection()
    set_fields: Dict[str, Any] = {
        "agent_logs.$.status": agent_status,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if message is not None:
        set_fields["agent_logs.$.message"] = message
    if started_at is not None:
        set_fields["agent_logs.$.started_at"] = started_at
    if finished_at is not None:
        set_fields["agent_logs.$.finished_at"] = finished_at

    await collection.update_one(
        {"_id": ObjectId(repo_id), "agent_logs.agent": agent_name},
        {"$set": set_fields},
    )
