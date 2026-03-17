"""
Agent Execution API router
Exposes agent execution data from logs via REST endpoints
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Path as PathParam
from bson import ObjectId

from backend.utils.logger import get_logger
from backend.agents.agent_log_parser import AgentLogParser
from backend.utils.db import get_repos_collection

router = APIRouter(prefix="/api/agents", tags=["agent-execution"])
logger = get_logger(__name__)

# Create global parser instance
log_parser = AgentLogParser()


async def _resolve_repo_scope(repo_id: Optional[str]) -> Optional[str]:
    if not repo_id:
        return None

    raw = repo_id.strip()
    if not raw:
        return None

    if ObjectId.is_valid(raw):
        try:
            collection = await get_repos_collection()
            doc = await collection.find_one({"_id": ObjectId(raw)}, {"repo_name": 1})
            if doc and doc.get("repo_name"):
                return str(doc["repo_name"])
        except Exception as exc:
            logger.warning(f"Unable to resolve repo_id {raw} to repo_name: {exc}")

    return raw


@router.get("/executions/recent")
async def get_recent_agent_executions(
    limit: int = Query(50, ge=1, le=500, description="Number of recent executions to return"),
) -> Dict[str, Any]:
    """
    Get recent agent executions from logs.
    
    This shows the latest agent operations including analysis, writing, verification.
    
    Args:
        limit: Number of recent executions (default 50, max 500)
        
    Returns:
        List of recent agent executions with timestamps and details
    """
    try:
        executions = log_parser.get_recent_executions(limit)
        
        return {
            "success": True,
            "total": len(executions),
            "data": [
                {
                    "timestamp": e.timestamp,
                    "agent": e.agent_name,
                    "component": e.component_name,
                    "action": e.action,
                    "status": e.status,
                    "message": e.message,
                }
                for e in executions
            ]
        }
    except Exception as e:
        logger.error(f"Error retrieving recent executions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving executions: {str(e)}"
        )


@router.get("/statistics")
async def get_agent_statistics(
    repo_id: Optional[str] = Query(None, description="Optional repository identifier to scope stats to latest run"),
) -> Dict[str, Any]:
    """
    Get aggregate statistics from all agent logs.
    
    Shows performance metrics including success rates, execution counts per agent.
    
    Returns:
        Statistics dictionary with agent breakdown
    """
    try:
        repo_scope = await _resolve_repo_scope(repo_id)
        stats = log_parser.get_agent_statistics(repo_id=repo_scope)
        
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error retrieving agent statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving statistics: {str(e)}"
        )


@router.get("/component/{component_id}/flow")
async def get_component_execution_flow(
    component_id: str = PathParam(..., description="Component ID"),
) -> Dict[str, Any]:
    """
    Get the complete execution flow for a specific component.
    
    Shows which agents executed, in what order, and the sequence of actions.
    
    Args:
        component_id: The ID of the component
        
    Returns:
        Component execution flow with all agent interactions
    """
    try:
        flow = log_parser.get_component_execution_flow(component_id)
        
        if "error" in flow:
            raise HTTPException(
                status_code=404,
                detail=flow["error"]
            )
        
        return {
            "success": True,
            "data": flow
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving component flow for {component_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving component flow: {str(e)}"
        )


@router.get("/component/all-flows")
async def get_all_component_flows(
    limit: int = Query(100, ge=1, le=1000, description="Maximum components to return"),
    repo_id: Optional[str] = Query(None, description="Optional repository identifier to scope flows to latest run"),
) -> Dict[str, Any]:
    """
    Get execution flows for all components from logs.
    
    Shows all components processed and their execution flows.
    
    Args:
        limit: Maximum number of components to return (default 100, max 1000)
        
    Returns:
        List of component flows
    """
    try:
        repo_scope = await _resolve_repo_scope(repo_id)
        flows = log_parser.get_all_component_flows(limit=limit, repo_id=repo_scope)
        
        return {
            "success": True,
            "total": len(flows),
            "data": flows
        }
    except Exception as e:
        logger.error(f"Error retrieving all component flows: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving component flows: {str(e)}"
        )


@router.get("/summary")
async def get_agent_execution_summary() -> Dict[str, Any]:
    """
    Get a summary of agent execution from logs.
    
    Combines recent executions and statistics for dashboard view.
    
    Returns:
        Summary dictionary with stats and recent activity
    """
    try:
        stats = log_parser.get_agent_statistics()
        recent = log_parser.get_recent_executions(limit=20)
        
        return {
            "success": True,
            "data": {
                "statistics": stats,
                "recent_executions": [
                    {
                        "timestamp": e.timestamp,
                        "agent": e.agent_name,
                        "component": e.component_name,
                        "action": e.action,
                        "status": e.status,
                    }
                    for e in recent
                ]
            }
        }
    except Exception as e:
        logger.error(f"Error retrieving execution summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving summary: {str(e)}"
        )


@router.get("/{agent_name}/logs")
async def get_agent_logs(
    agent_name: str = PathParam(..., description="Agent name (reader, searcher, writer, verifier)"),
) -> Dict[str, Any]:
    """
    Get logs for a specific agent.
    
    Args:
        agent_name: Name of the agent (reader, searcher, writer, or verifier)
        
    Returns:
        Parsed executions from that agent's logs
    """
    try:
        # Validate agent name
        valid_agents = ["reader", "searcher", "writer", "verifier"]
        if agent_name not in valid_agents:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent name. Must be one of: {', '.join(valid_agents)}"
            )
        
        # Get agent logs from orchestrator log
        by_agent = log_parser.parse_orchestrator_logs()
        
        if agent_name not in by_agent:
            return {
                "success": True,
                "agent": agent_name,
                "total": 0,
                "data": []
            }
        
        executions = by_agent[agent_name]
        
        return {
            "success": True,
            "agent": agent_name,
            "total": len(executions),
            "data": [
                {
                    "timestamp": e.timestamp,
                    "action": e.action,
                    "component": e.component_name,
                    "message": e.message,
                    "status": e.status,
                }
                for e in executions
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving {agent_name} logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving agent logs: {str(e)}"
        )