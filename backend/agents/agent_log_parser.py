"""
Agent Execution Log Parser
Parses agent log files to extract execution flow and data
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import re
from dataclasses import dataclass, asdict

from backend.utils.logger import get_logger
from backend.utils.paths import DATA_ROOT

logger = get_logger(__name__)


@dataclass
class AgentExecution:
    """Represents a single agent execution"""
    timestamp: str
    agent_name: str
    component_id: Optional[str]
    component_name: Optional[str]
    action: str  # e.g., "analyzing", "complete", "error"
    message: str
    metadata: Dict[str, Any]
    duration_ms: Optional[int] = None
    status: str = "success"  # success or failed


class AgentLogParser:
    """
    Parses agent log files to extract execution information
    """
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.logger = get_logger("log_parser")
        
        # Regex patterns to parse log entries
        self.log_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([\w.]+) - (\w+) - (.*)'
        )
        self.ansi_pattern = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        self.processing_component_pattern = re.compile(
            r'Processing component\s+\d+/\d+:\s+([^\(]+)\s*\(',
            re.IGNORECASE,
        )
        self.component_id_pattern = re.compile(r'component_id:\s*([\w.\-/:]+)', re.IGNORECASE)
        self.component_for_pattern = re.compile(
            r'(?:analyzing|documentation\s+for|verifying\s+documentation\s+for|complete\s+for|failed\s+to\s+document)\s*:?\s*([A-Za-z_][\w.$-]*)',
            re.IGNORECASE,
        )
        self.pipeline_start_pattern = re.compile(
            r'Starting pipeline for repository:\s*(.+)$',
            re.IGNORECASE,
        )

    def _parse_timestamp(self, timestamp: str) -> Optional[datetime]:
        try:
            return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            return None

    def _repo_matches(self, requested_repo_id: str, repository_path: str) -> bool:
        if not requested_repo_id or not repository_path:
            return False

        requested = requested_repo_id.strip().lower()
        normalized_repo_path = repository_path.replace("/", "\\").strip().lower()
        repository_name = Path(normalized_repo_path).name.lower()

        return (
            repository_name == requested
            or normalized_repo_path.endswith(f"\\{requested}")
            or requested in repository_name
        )

    def _get_latest_repo_window(self, repo_id: str) -> Optional[tuple[datetime, Optional[datetime]]]:
        pipeline_log = self.log_dir / "backend.pipeline.log"
        if not pipeline_log.exists() or not repo_id:
            return None

        starts: List[tuple[datetime, str]] = []

        try:
            with open(pipeline_log, "r", encoding="utf-8") as file_handle:
                for raw_line in file_handle:
                    clean_line = self._strip_ansi(raw_line)
                    match = self.log_pattern.match(clean_line)
                    if not match:
                        continue

                    timestamp, logger_name, _, message = match.groups()
                    if "pipeline" not in logger_name:
                        continue

                    start_match = self.pipeline_start_pattern.search(message)
                    if not start_match:
                        continue

                    start_ts = self._parse_timestamp(timestamp)
                    if not start_ts:
                        continue

                    repo_path = start_match.group(1).strip()
                    starts.append((start_ts, repo_path))
        except Exception as exc:
            self.logger.error(f"Error reading pipeline log for repo window: {exc}")
            return None

        if not starts:
            return None

        starts.sort(key=lambda item: item[0])

        latest_index: Optional[int] = None
        for index, (_, repo_path) in enumerate(starts):
            if self._repo_matches(repo_id, repo_path):
                latest_index = index

        if latest_index is None:
            return None

        start_time = starts[latest_index][0]
        end_time: Optional[datetime] = None
        for next_index in range(latest_index + 1, len(starts)):
            candidate = starts[next_index][0]
            if candidate > start_time:
                end_time = candidate
                break

        return (start_time, end_time)

    def _filter_executions_by_repo(self, executions: List[AgentExecution], repo_id: Optional[str]) -> List[AgentExecution]:
        if not repo_id:
            return executions

        window = self._get_latest_repo_window(repo_id)
        if not window:
            return []

        start_time, end_time = window
        filtered: List[AgentExecution] = []

        for execution in executions:
            execution_ts = self._parse_timestamp(execution.timestamp)
            if not execution_ts:
                continue

            if execution_ts < start_time:
                continue

            if end_time and execution_ts >= end_time:
                continue

            filtered.append(execution)

        return filtered

    def _strip_ansi(self, text: str) -> str:
        return self.ansi_pattern.sub("", text).strip()

    def _extract_component_name(self, message: str) -> Optional[str]:
        if not message:
            return None

        msg = message.strip()

        match = self.component_id_pattern.search(msg)
        if match:
            return match.group(1).strip()

        match = self.processing_component_pattern.search(msg)
        if match:
            return match.group(1).strip()

        match = self.component_for_pattern.search(msg)
        if match:
            return match.group(1).strip()

        return None

    def _message_mentions_component(self, message: str, component_id: str) -> bool:
        """Match component id as a token, not as a substring inside paths/words."""
        if not message or not component_id:
            return False

        escaped_component = re.escape(component_id)
        token_pattern = re.compile(rf'(?<![A-Za-z0-9_]){escaped_component}(?![A-Za-z0-9_])')
        return bool(token_pattern.search(message))

    def _get_execution_logs(self) -> List[Path]:
        """Get the most relevant logs for component flow extraction."""
        candidates = [
            self.log_dir / "orchestrator.log",
            self.log_dir / "agent.reader.log",
            self.log_dir / "agent.searcher.log",
            self.log_dir / "agent.writer.log",
            self.log_dir / "agent.verifier.log",
            self.log_dir / "backend.pipeline.log",
        ]
        return [path for path in candidates if path.exists()]

    def _collect_executions(self) -> List[AgentExecution]:
        """Collect executions from all relevant logs."""
        executions: List[AgentExecution] = []
        for log_file in self._get_execution_logs():
            executions.extend(self.parse_log_file(log_file))
        return executions
    
    def get_agent_logs(self, agent_name: Optional[str] = None) -> List[Path]:
        """
        Get log files for agents.
        
        Args:
            agent_name: Specific agent (reader, searcher, writer, verifier) or None for all
            
        Returns:
            List of log file paths
        """
        if not self.log_dir.exists():
            self.logger.warning(f"Log directory not found: {self.log_dir}")
            return []
        
        if agent_name:
            # Search for agent-specific log
            agent_log = self.log_dir / f"agent.{agent_name}.log"
            if agent_log.exists():
                return [agent_log]
            
            # Also check for generic patterns
            log_file = self.log_dir / f"{agent_name}.log"
            if log_file.exists():
                return [log_file]
            
            return []
        else:
            # Get all agent logs
            agent_logs = list(self.log_dir.glob("agent.*.log"))
            agent_logs.extend(self.log_dir.glob("reader.log"))
            agent_logs.extend(self.log_dir.glob("searcher.log"))
            agent_logs.extend(self.log_dir.glob("writer.log"))
            agent_logs.extend(self.log_dir.glob("verifier.log"))
            
            return sorted(set(agent_logs))
    
    def parse_log_file(self, log_file: Path) -> List[AgentExecution]:
        """
        Parse a log file and extract executions.
        
        Args:
            log_file: Path to log file
            
        Returns:
            List of AgentExecution objects
        """
        executions = []
        
        if not log_file.exists():
            self.logger.warning(f"Log file not found: {log_file}")
            return executions
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                execution = self._parse_log_line(line)
                if execution:
                    executions.append(execution)
        
        except Exception as e:
            self.logger.error(f"Error parsing log file {log_file}: {e}")
        
        return executions
    
    def _parse_log_line(self, line: str) -> Optional[AgentExecution]:
        """
        Parse a single log line.
        
        Args:
            line: Raw log line
            
        Returns:
            AgentExecution object or None if not parseable
        """
        clean_line = self._strip_ansi(line)
        match = self.log_pattern.match(clean_line)
        if not match:
            return None
        
        timestamp, logger_name, level, message = match.groups()
        
        # Extract agent name from logger name
        agent_name = None
        if 'agent.' in logger_name:
            agent_name = logger_name.split('agent.')[-1]
        elif any(x in logger_name for x in ['reader', 'searcher', 'writer', 'verifier']):
            agent_name = logger_name.split('.')[-1]
        elif 'orchestrator' in logger_name:
            agent_name = 'orchestrator'
        elif 'pipeline' in logger_name:
            agent_name = 'pipeline'
        
        if not agent_name:
            return None

        agent_name = agent_name.lower()
        
        # Parse message to extract metadata
        component_id = None
        component_name = None
        action = "executing"
        status = "success" if level != "ERROR" else "failed"
        
        # Extract component info from message
        extracted_component = self._extract_component_name(message)
        if extracted_component:
            component_name = extracted_component
            component_id = extracted_component

        if "component" in message.lower() or "analyzing" in message.lower():
            action = "analyzing"
        if "processing component" in message.lower() or "generating documentation" in message.lower() or "verifying documentation" in message.lower():
            action = "analyzing"
        
        if "complete" in message.lower():
            action = "completed"
        
        if "error" in message.lower() or level == "ERROR":
            action = "error"
            status = "failed"
        
        return AgentExecution(
            timestamp=timestamp,
            agent_name=agent_name,
            component_id=component_id,
            component_name=component_name,
            action=action,
            message=message,
            metadata={
                'logger_name': logger_name,
                'level': level,
            },
            status=status
        )
    
    def parse_orchestrator_logs(self, repo_id: Optional[str] = None) -> Dict[str, List[AgentExecution]]:
        """
        Parse all orchestrator logs to extract execution flow.
        
        Returns:
            Dict mapping agent names to their executions
        """
        executions = self._filter_executions_by_repo(self._collect_executions(), repo_id)
        if not executions:
            self.logger.warning("No execution logs found")
            return {}
        
        # Group by agent
        by_agent = {}
        for execution in executions:
            if execution.agent_name:
                if execution.agent_name not in by_agent:
                    by_agent[execution.agent_name] = []
                by_agent[execution.agent_name].append(execution)
        
        return by_agent
    
    def get_component_execution_flow(self, component_id: str, repo_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the complete execution flow for a component from logs.
        
        Args:
            component_id: Component ID to search for
            
        Returns:
            Dict with execution flow information
        """
        executions = self._filter_executions_by_repo(self._collect_executions(), repo_id)
        if not executions:
            self.logger.warning("No execution logs found")
            return {"error": "No execution logs found"}
        
        # Filter for this component
        component_executions = [
            e for e in executions 
            if self._message_mentions_component(e.message, component_id)
            or (e.component_id and e.component_id == component_id)
            or (e.component_name and e.component_name == component_id)
        ]
        
        if not component_executions:
            return {"error": f"No executions found for component {component_id}"}
        
        # Extract flow information
        inferred_agents = set()
        for execution in component_executions:
            message_lower = execution.message.lower()
            if "reader-searcher converged" in message_lower:
                inferred_agents.update({"reader", "searcher"})
            if "reader" in message_lower and "searcher" not in message_lower:
                inferred_agents.add("reader")
            if "searcher" in message_lower and "reader" not in message_lower:
                inferred_agents.add("searcher")
            if "writer" in message_lower:
                inferred_agents.add("writer")
            if "verifier" in message_lower:
                inferred_agents.add("verifier")

        explicit_agents = set(
            e.agent_name
            for e in component_executions
            if e.agent_name and e.agent_name not in {"orchestrator", "pipeline"}
        )

        flow = {
            "component_id": component_id,
            "executions": [asdict(e) for e in component_executions],
            "agents_involved": sorted(list(explicit_agents.union(inferred_agents))),
            "total_executions": len(component_executions),
            "status": "failed" if any(e.status == "failed" for e in component_executions) else "success",
        }
        
        return flow
    
    def get_all_component_flows(self, limit: int = 100, repo_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get execution flows for all components from logs.
        
        Args:
            limit: Maximum number of components to return
            
        Returns:
            List of component flows
        """
        executions = self._filter_executions_by_repo(self._collect_executions(), repo_id)
        if not executions:
            self.logger.warning("No execution logs found")
            return []
        
        # Extract component IDs from messages
        component_ids = set()
        for execution in executions:
            if execution.component_id:
                component_ids.add(execution.component_id)
            if execution.component_name:
                component_ids.add(execution.component_name)

            extracted_component = self._extract_component_name(execution.message)
            if extracted_component:
                component_ids.add(extracted_component)
        
        # Get flows for each component
        flows = []
        for comp_id in sorted(list(component_ids))[:limit]:
            flow = self.get_component_execution_flow(comp_id, repo_id=repo_id)
            if "error" not in flow:
                flows.append(flow)
        
        return flows
    
    def get_agent_statistics(self, repo_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics from all agent logs.
        
        Returns:
            Statistics dictionary
        """
        by_agent = self.parse_orchestrator_logs(repo_id=repo_id)
        
        stats = {
            "total_executions": 0,
            "by_agent": {},
            "success_count": 0,
            "failure_count": 0,
        }
        
        for agent_name, executions in by_agent.items():
            stats["by_agent"][agent_name] = {
                "total": len(executions),
                "completed": len([e for e in executions if e.action == "completed"]),
                "errors": len([e for e in executions if e.status == "failed"]),
            }
            stats["total_executions"] += len(executions)
            stats["success_count"] += len([e for e in executions if e.status == "success"])
            stats["failure_count"] += len([e for e in executions if e.status == "failed"])
        
        stats["success_rate"] = round(
            (stats["success_count"] / max(stats["total_executions"], 1)) * 100,
            2
        )
        
        return stats
    
    def get_recent_executions(self, limit: int = 50) -> List[AgentExecution]:
        """
        Get recent agent executions.
        
        Args:
            limit: Number of recent executions to return
            
        Returns:
            List of recent AgentExecution objects
        """
        orchestrator_log = self.log_dir / "orchestrator.log"
        
        if not orchestrator_log.exists():
            return []
        
        executions = self.parse_log_file(orchestrator_log)
        
        # Return most recent
        return executions[-limit:] if len(executions) > limit else executions