#!/usr/bin/env python3
"""
Agent Performance Evaluation Script
====================================

Evaluates the Code_IQ agent pipeline's performance across multiple metrics:

1. Learning Curve (Improvement Rate) - How documentation quality improves across iterations
2. Critical Error Rate (Tool/Failure) - Rate of agent failures and tool errors
3. Hallucination Rate (LLM agents) - Rate of fabricated/incorrect information
4. Misalignment Incidents - Cases where agents deviate from instructions
5. Collaboration Score (Interaction) - Quality of inter-agent communication
6. Response Latency - Time taken for agent responses
7. Instruction Following Accuracy - How well agents follow their prompts
8. Action Justification Score (Explainability) - Quality of agent reasoning explanations
9. Transparency of Reasoning - Clarity and traceability of agent decisions

Usage:
    # Evaluate with multiple repositories
    python scripts/evaluate_agent_performance.py --repos repo1,repo2,repo3

    # Evaluate with a single repository
    python scripts/evaluate_agent_performance.py --repos https://github.com/user/repo

    # Use existing pipeline outputs
    python scripts/evaluate_agent_performance.py --repos my-repo --use-existing

Output:
    - Detailed metrics saved to: data/agent_evaluation/{timestamp}/
    - Summary report: agent_performance_report.json
    - Human-readable: agent_performance_report.md
"""

import os
import sys
import json
import time
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import traceback

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.paths import DATA_ROOT
from backend.utils.logger import get_logger
from backend.agents.agent_log_parser import AgentLogParser, AgentExecution

logger = get_logger(__name__)


# =============================================================================
# Data Classes for Metrics
# =============================================================================

@dataclass
class LearningCurveMetrics:
    """Metrics for tracking improvement over iterations"""
    improvement_rate: float = 0.0
    initial_quality: float = 0.0
    final_quality: float = 0.0
    quality_by_iteration: List[float] = field(default_factory=list)
    convergence_iteration: int = 0
    trend: str = "neutral"  # improving, declining, stable, neutral


@dataclass
class ErrorRateMetrics:
    """Metrics for error tracking"""
    total_executions: int = 0
    critical_errors: int = 0
    tool_failures: int = 0
    recoverable_errors: int = 0
    critical_error_rate: float = 0.0
    tool_failure_rate: float = 0.0
    recovery_rate: float = 0.0
    errors_by_agent: Dict[str, int] = field(default_factory=dict)
    error_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class HallucinationMetrics:
    """Metrics for hallucination detection"""
    total_mentions: int = 0
    hallucinated_mentions: int = 0
    hallucination_rate: float = 0.0
    hallucinations_by_type: Dict[str, int] = field(default_factory=dict)
    worst_components: List[Dict[str, Any]] = field(default_factory=list)
    average_existence_ratio: float = 0.0


@dataclass
class MisalignmentMetrics:
    """Metrics for instruction misalignment"""
    total_instructions: int = 0
    misalignment_incidents: int = 0
    misalignment_rate: float = 0.0
    misalignment_by_agent: Dict[str, int] = field(default_factory=dict)
    misalignment_types: Dict[str, int] = field(default_factory=dict)
    severity_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class CollaborationMetrics:
    """Metrics for inter-agent collaboration"""
    total_interactions: int = 0
    successful_handoffs: int = 0
    failed_handoffs: int = 0
    collaboration_score: float = 0.0
    context_utilization_rate: float = 0.0
    reader_searcher_iterations: int = 0
    verifier_rejection_rate: float = 0.0
    agent_interaction_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)


@dataclass
class LatencyMetrics:
    """Metrics for response timing"""
    total_time_seconds: float = 0.0
    average_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    latency_by_agent: Dict[str, float] = field(default_factory=dict)
    latency_trend: str = "stable"


@dataclass
class InstructionFollowingMetrics:
    """Metrics for instruction adherence"""
    total_instructions: int = 0
    followed_correctly: int = 0
    partially_followed: int = 0
    not_followed: int = 0
    accuracy_rate: float = 0.0
    accuracy_by_agent: Dict[str, float] = field(default_factory=dict)
    common_deviations: List[str] = field(default_factory=list)


@dataclass
class ExplainabilityMetrics:
    """Metrics for action justification and explainability"""
    total_actions: int = 0
    justified_actions: int = 0
    unjustified_actions: int = 0
    justification_score: float = 0.0
    justification_by_agent: Dict[str, float] = field(default_factory=dict)
    reasoning_clarity_score: float = 0.0


@dataclass
class TransparencyMetrics:
    """Metrics for reasoning transparency"""
    total_decisions: int = 0
    transparent_decisions: int = 0
    opaque_decisions: int = 0
    transparency_score: float = 0.0
    traceable_steps: int = 0
    traceability_rate: float = 0.0
    reasoning_depth_avg: float = 0.0


@dataclass
class AgentPerformanceReport:
    """Complete performance evaluation report"""
    repo_name: str
    evaluation_timestamp: str
    total_components: int
    
    learning_curve: LearningCurveMetrics = field(default_factory=LearningCurveMetrics)
    error_rate: ErrorRateMetrics = field(default_factory=ErrorRateMetrics)
    hallucination: HallucinationMetrics = field(default_factory=HallucinationMetrics)
    misalignment: MisalignmentMetrics = field(default_factory=MisalignmentMetrics)
    collaboration: CollaborationMetrics = field(default_factory=CollaborationMetrics)
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)
    instruction_following: InstructionFollowingMetrics = field(default_factory=InstructionFollowingMetrics)
    explainability: ExplainabilityMetrics = field(default_factory=ExplainabilityMetrics)
    transparency: TransparencyMetrics = field(default_factory=TransparencyMetrics)
    
    overall_score: float = 0.0
    grade: str = "N/A"
    recommendations: List[str] = field(default_factory=list)


# =============================================================================
# Agent Performance Evaluator
# =============================================================================

class AgentPerformanceEvaluator:
    """
    Comprehensive evaluator for agent pipeline performance.
    Analyzes logs, outputs, and metrics to provide insights.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        verbose: bool = True
    ):
        self.verbose = verbose
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = DATA_ROOT / "agent_evaluation" / self.timestamp
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize log parser
        self.log_parser = AgentLogParser(log_dir=str(PROJECT_ROOT / "logs"))
        
        # Data paths
        self.writer_output_dir = DATA_ROOT / "intermediate" / "agent_output" / "writer"
        self.verifier_output_dir = DATA_ROOT / "intermediate" / "agent_output" / "verifier"
        self.navigator_output_dir = DATA_ROOT / "intermediate" / "navigator_output"
        self.validation_dir = DATA_ROOT / "validation"
        
        self.reports: List[AgentPerformanceReport] = []
    
    def _log(self, message: str, level: str = "INFO"):
        """Log message"""
        if self.verbose:
            print(f"[{level}] {message}")
        if level == "INFO":
            logger.info(message)
        elif level == "WARN":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
    
    # =========================================================================
    # Metric Calculators
    # =========================================================================
    
    def _calculate_learning_curve(
        self,
        repo_name: str,
        executions: List[AgentExecution]
    ) -> LearningCurveMetrics:
        """
        Calculate learning curve metrics based on quality improvements
        across iterations and verifier feedback.
        """
        metrics = LearningCurveMetrics()
        
        # Load verifier output to track improvement
        verifier_file = self.verifier_output_dir / f"{repo_name}_verifier_output.json"
        if not verifier_file.exists():
            verifier_files = list(self.verifier_output_dir.glob(f"*{repo_name}*.json"))
            verifier_file = verifier_files[0] if verifier_files else None
        
        quality_scores = []
        
        if verifier_file and verifier_file.exists():
            try:
                with open(verifier_file, 'r', encoding='utf-8') as f:
                    verifier_data = json.load(f)
                
                # Extract quality scores from verifier output
                for comp_id, comp_data in verifier_data.items():
                    if isinstance(comp_data, dict):
                        score = comp_data.get('quality_score', comp_data.get('score', 0))
                        if score:
                            quality_scores.append(float(score))
            except Exception as e:
                self._log(f"Error loading verifier output: {e}", "WARN")
        
        # Also check unified evaluation results
        eval_file = self.validation_dir / repo_name / "unified_evaluation_results.json"
        if eval_file.exists():
            try:
                with open(eval_file, 'r', encoding='utf-8') as f:
                    eval_data = json.load(f)
                
                overall_score = eval_data.get('overall_quality_score', 0)
                if overall_score:
                    quality_scores.append(overall_score)
            except Exception as e:
                self._log(f"Error loading evaluation results: {e}", "WARN")
        
        # Calculate metrics
        if quality_scores:
            metrics.quality_by_iteration = quality_scores
            metrics.initial_quality = quality_scores[0] if quality_scores else 0
            metrics.final_quality = quality_scores[-1] if quality_scores else 0
            
            if len(quality_scores) > 1:
                metrics.improvement_rate = (metrics.final_quality - metrics.initial_quality) / metrics.initial_quality if metrics.initial_quality > 0 else 0
                
                # Determine trend
                if metrics.improvement_rate > 0.1:
                    metrics.trend = "improving"
                elif metrics.improvement_rate < -0.1:
                    metrics.trend = "declining"
                else:
                    metrics.trend = "stable"
                
                # Find convergence point
                for i in range(len(quality_scores) - 1):
                    if abs(quality_scores[i+1] - quality_scores[i]) < 0.01:
                        metrics.convergence_iteration = i + 1
                        break
                else:
                    metrics.convergence_iteration = len(quality_scores)
        
        return metrics
    
    def _calculate_error_rate(
        self,
        repo_name: str,
        executions: List[AgentExecution]
    ) -> ErrorRateMetrics:
        """Calculate error and failure rates from execution logs."""
        metrics = ErrorRateMetrics()
        
        metrics.total_executions = len(executions)
        
        for execution in executions:
            agent = execution.agent_name or "unknown"
            
            # Track errors by agent
            if agent not in metrics.errors_by_agent:
                metrics.errors_by_agent[agent] = 0
            
            # Check for errors
            if execution.status == "failed":
                metrics.errors_by_agent[agent] += 1
                
                # Categorize error type
                message = (execution.message or "").lower()
                
                if any(kw in message for kw in ['critical', 'fatal', 'crash', 'exception']):
                    metrics.critical_errors += 1
                    error_type = "critical"
                elif any(kw in message for kw in ['tool', 'llm', 'api', 'timeout', 'connection']):
                    metrics.tool_failures += 1
                    error_type = "tool_failure"
                else:
                    metrics.recoverable_errors += 1
                    error_type = "recoverable"
                
                metrics.error_types[error_type] = metrics.error_types.get(error_type, 0) + 1
        
        # Calculate rates
        total = max(metrics.total_executions, 1)
        metrics.critical_error_rate = metrics.critical_errors / total
        metrics.tool_failure_rate = metrics.tool_failures / total
        
        total_errors = metrics.critical_errors + metrics.tool_failures + metrics.recoverable_errors
        if total_errors > 0:
            metrics.recovery_rate = metrics.recoverable_errors / total_errors
        
        return metrics
    
    def _calculate_hallucination_rate(
        self,
        repo_name: str
    ) -> HallucinationMetrics:
        """
        Calculate hallucination metrics from truthfulness evaluation.
        Uses existing truthfulness evaluation results if available.
        """
        metrics = HallucinationMetrics()
        
        # Check for existing truthfulness evaluation
        truthfulness_file = self.validation_dir / repo_name / "truthfulness_report.md"
        eval_file = self.validation_dir / repo_name / "unified_evaluation_results.json"
        
        if eval_file.exists():
            try:
                with open(eval_file, 'r', encoding='utf-8') as f:
                    eval_data = json.load(f)
                
                truthfulness_data = eval_data.get('truthfulness', {}).get('summary', {})
                
                metrics.total_mentions = truthfulness_data.get('total_mentions', 0)
                metrics.hallucinated_mentions = truthfulness_data.get('components_with_issues', 0)
                
                accuracy = truthfulness_data.get('overall_accuracy')
                if metrics.total_mentions:
                    metrics.hallucination_rate = metrics.hallucinated_mentions / max(metrics.total_mentions, 1)
                    metrics.average_existence_ratio = 1.0 - metrics.hallucination_rate
                elif accuracy is not None:
                    metrics.hallucination_rate = 1.0 - float(accuracy)
                    metrics.average_existence_ratio = float(accuracy)
                
                # Extract issue types
                issue_types = truthfulness_data.get('issue_types', {})
                metrics.hallucinations_by_type = issue_types
                
            except Exception as e:
                self._log(f"Error loading truthfulness data: {e}", "WARN")
        
        # If no evaluation exists, try to run one
        if metrics.total_mentions == 0:
            try:
                from backend.evaluator.truthfulness import TruthfulnessEvaluator
                
                evaluator = TruthfulnessEvaluator(
                    writer_output_dir=str(self.writer_output_dir),
                    navigator_output_dir=str(self.navigator_output_dir),
                    use_llm=False,  # Fast mode
                    repository_name=repo_name
                )
                
                results = evaluator.evaluate_all()
                
                if results:
                    total_mentions = sum(r.total_mentions for r in results.values())
                    hallucinated = sum(
                        len([m for m in r.mentioned_components if not m.exists])
                        for r in results.values()
                    )
                    
                    metrics.total_mentions = total_mentions
                    metrics.hallucinated_mentions = hallucinated
                    metrics.hallucination_rate = hallucinated / max(total_mentions, 1)
                    metrics.average_existence_ratio = 1.0 - metrics.hallucination_rate
                    
            except Exception as e:
                self._log(f"Could not run truthfulness evaluation: {e}", "WARN")
        
        return metrics
    
    def _calculate_misalignment(
        self,
        repo_name: str,
        executions: List[AgentExecution]
    ) -> MisalignmentMetrics:
        """
        Calculate misalignment metrics by analyzing agent outputs
        against expected behavior patterns.
        """
        metrics = MisalignmentMetrics()
        
        # Load writer output to check for format/instruction adherence
        writer_file = self.writer_output_dir / f"{repo_name}_writer_output.json"
        if not writer_file.exists():
            writer_files = list(self.writer_output_dir.glob(f"*{repo_name}*.json"))
            writer_file = writer_files[0] if writer_files else None
        
        if writer_file and writer_file.exists():
            try:
                with open(writer_file, 'r', encoding='utf-8') as f:
                    writer_data = json.load(f)
                
                for comp_id, comp_data in writer_data.items():
                    metrics.total_instructions += 1
                    
                    docstring = comp_data.get('docstring', '') if isinstance(comp_data, dict) else ''
                    
                    # Check for misalignment indicators
                    misaligned = False
                    
                    # Check 1: Empty or trivial docstring
                    if len(docstring.strip()) < 20:
                        misaligned = True
                        metrics.misalignment_types['empty_output'] = metrics.misalignment_types.get('empty_output', 0) + 1
                    
                    # Check 2: Contains system prompt leakage
                    if any(kw in docstring.lower() for kw in ['as an ai', 'i am a', 'language model', 'i cannot']):
                        misaligned = True
                        metrics.misalignment_types['system_leakage'] = metrics.misalignment_types.get('system_leakage', 0) + 1
                    
                    # Check 3: Wrong format (e.g., not proper docstring format)
                    if docstring and not any(tag in docstring for tag in ['Args:', 'Returns:', '@param', '@returns', 'Parameters', ':param']):
                        # Might be missing required sections
                        if 'def ' in str(comp_data.get('source_code', '')) or 'function' in str(comp_data.get('type', '')).lower():
                            misaligned = True
                            metrics.misalignment_types['missing_sections'] = metrics.misalignment_types.get('missing_sections', 0) + 1
                    
                    if misaligned:
                        metrics.misalignment_incidents += 1
                        metrics.misalignment_by_agent['writer'] = metrics.misalignment_by_agent.get('writer', 0) + 1
                
            except Exception as e:
                self._log(f"Error analyzing misalignment: {e}", "WARN")
        
        # Check verifier rejections as misalignment indicators
        verifier_rejections = len([
            e for e in executions
            if e.agent_name == 'verifier' and 'reject' in (e.message or '').lower()
        ])
        
        if verifier_rejections > 0:
            metrics.misalignment_by_agent['verifier_rejections'] = verifier_rejections
            metrics.misalignment_types['quality_rejection'] = verifier_rejections
        
        metrics.misalignment_rate = metrics.misalignment_incidents / max(metrics.total_instructions, 1)
        
        return metrics
    
    def _calculate_collaboration(
        self,
        repo_name: str,
        executions: List[AgentExecution]
    ) -> CollaborationMetrics:
        """Calculate collaboration and interaction metrics between agents."""
        metrics = CollaborationMetrics()
        
        # Build agent interaction matrix
        agents = ['reader', 'searcher', 'writer', 'verifier']
        for agent in agents:
            metrics.agent_interaction_matrix[agent] = {a: 0 for a in agents}
        
        # Track handoffs
        prev_agent = None
        for execution in executions:
            agent = execution.agent_name
            if agent not in agents:
                continue
            
            metrics.total_interactions += 1
            
            if prev_agent and prev_agent != agent:
                # This is a handoff
                if prev_agent in metrics.agent_interaction_matrix:
                    metrics.agent_interaction_matrix[prev_agent][agent] += 1
                
                # Check if handoff was successful (no error in current execution)
                if execution.status == "success":
                    metrics.successful_handoffs += 1
                else:
                    metrics.failed_handoffs += 1
            
            prev_agent = agent
        
        # Count reader-searcher iterations
        reader_count = len([e for e in executions if e.agent_name == 'reader'])
        searcher_count = len([e for e in executions if e.agent_name == 'searcher'])
        metrics.reader_searcher_iterations = min(reader_count, searcher_count)
        
        # Calculate verifier rejection rate
        verifier_executions = [e for e in executions if e.agent_name == 'verifier']
        verifier_rejections = len([
            e for e in verifier_executions
            if 'reject' in (e.message or '').lower() or 'revision' in (e.message or '').lower()
        ])
        
        if verifier_executions:
            metrics.verifier_rejection_rate = verifier_rejections / len(verifier_executions)
        
        # Calculate collaboration score
        total_handoffs = metrics.successful_handoffs + metrics.failed_handoffs
        if total_handoffs > 0:
            handoff_success_rate = metrics.successful_handoffs / total_handoffs
            # Penalize high rejection rates
            rejection_penalty = metrics.verifier_rejection_rate * 0.3
            metrics.collaboration_score = max(0, handoff_success_rate - rejection_penalty)
        
        # Context utilization
        context_used = len([
            e for e in executions
            if any(kw in (e.message or '').lower() for kw in ['context', 'dependency', 'reference'])
        ])
        metrics.context_utilization_rate = context_used / max(metrics.total_interactions, 1)
        
        return metrics
    
    def _calculate_latency(
        self,
        repo_name: str,
        executions: List[AgentExecution]
    ) -> LatencyMetrics:
        """Calculate response latency metrics."""
        metrics = LatencyMetrics()
        
        latencies = []
        agent_latencies = defaultdict(list)
        
        # Parse timestamps to calculate latencies
        prev_time = None
        for execution in executions:
            try:
                current_time = datetime.strptime(execution.timestamp, "%Y-%m-%d %H:%M:%S")
                
                if prev_time:
                    delta_ms = (current_time - prev_time).total_seconds() * 1000
                    if 0 < delta_ms < 300000:  # Reasonable range (0-5 minutes)
                        latencies.append(delta_ms)
                        if execution.agent_name:
                            agent_latencies[execution.agent_name].append(delta_ms)
                
                prev_time = current_time
            except (ValueError, TypeError):
                continue
        
        if latencies:
            latencies.sort()
            n = len(latencies)
            
            metrics.average_latency_ms = sum(latencies) / n
            metrics.min_latency_ms = latencies[0]
            metrics.max_latency_ms = latencies[-1]
            metrics.p50_latency_ms = latencies[n // 2]
            metrics.p90_latency_ms = latencies[int(n * 0.9)]
            metrics.p99_latency_ms = latencies[int(n * 0.99)] if n > 100 else latencies[-1]
            metrics.total_time_seconds = sum(latencies) / 1000
        
        # Per-agent latencies
        for agent, lats in agent_latencies.items():
            if lats:
                metrics.latency_by_agent[agent] = sum(lats) / len(lats)
        
        return metrics
    
    def _calculate_instruction_following(
        self,
        repo_name: str,
        executions: List[AgentExecution]
    ) -> InstructionFollowingMetrics:
        """Calculate instruction following accuracy."""
        metrics = InstructionFollowingMetrics()
        
        # Load writer output to analyze instruction adherence
        writer_file = self.writer_output_dir / f"{repo_name}_writer_output.json"
        if not writer_file.exists():
            writer_files = list(self.writer_output_dir.glob(f"*{repo_name}*.json"))
            writer_file = writer_files[0] if writer_files else None
        
        if writer_file and writer_file.exists():
            try:
                with open(writer_file, 'r', encoding='utf-8') as f:
                    writer_data = json.load(f)
                
                for comp_id, comp_data in writer_data.items():
                    metrics.total_instructions += 1
                    
                    docstring = comp_data.get('docstring', '') if isinstance(comp_data, dict) else ''
                    
                    # Check instruction adherence
                    if len(docstring.strip()) > 50:
                        # Has description - check for required sections
                        has_params = any(tag in docstring for tag in ['Args:', '@param', ':param', 'Parameters'])
                        has_returns = any(tag in docstring for tag in ['Returns:', '@returns', '@return', ':returns'])
                        
                        if has_params and has_returns:
                            metrics.followed_correctly += 1
                        elif has_params or has_returns:
                            metrics.partially_followed += 1
                        else:
                            metrics.not_followed += 1
                    else:
                        metrics.not_followed += 1
                
            except Exception as e:
                self._log(f"Error analyzing instruction following: {e}", "WARN")
        
        # Calculate accuracy
        metrics.accuracy_rate = metrics.followed_correctly / max(metrics.total_instructions, 1)
        
        # Analyze by agent from logs
        agent_success = defaultdict(lambda: {'total': 0, 'success': 0})
        for execution in executions:
            agent = execution.agent_name
            if agent in ['reader', 'searcher', 'writer', 'verifier']:
                agent_success[agent]['total'] += 1
                if execution.status == 'success' and execution.action == 'completed':
                    agent_success[agent]['success'] += 1
        
        for agent, stats in agent_success.items():
            if stats['total'] > 0:
                metrics.accuracy_by_agent[agent] = stats['success'] / stats['total']
        
        return metrics
    
    def _calculate_explainability(
        self,
        repo_name: str,
        executions: List[AgentExecution]
    ) -> ExplainabilityMetrics:
        """Calculate action justification and explainability scores."""
        metrics = ExplainabilityMetrics()
        
        # Analyze log messages for reasoning/justification
        reasoning_keywords = [
            'because', 'since', 'therefore', 'thus', 'due to', 'as a result',
            'reason', 'determined', 'concluded', 'analysis shows', 'found that'
        ]
        
        for execution in executions:
            if execution.agent_name in ['reader', 'searcher', 'writer', 'verifier']:
                metrics.total_actions += 1
                
                message = (execution.message or '').lower()
                
                # Check for justification in message
                has_justification = any(kw in message for kw in reasoning_keywords)
                
                if has_justification:
                    metrics.justified_actions += 1
                else:
                    metrics.unjustified_actions += 1
        
        # Calculate scores
        metrics.justification_score = metrics.justified_actions / max(metrics.total_actions, 1)
        
        # Load verifier output for reasoning clarity
        verifier_file = self.verifier_output_dir / f"{repo_name}_verifier_output.json"
        if not verifier_file.exists():
            verifier_files = list(self.verifier_output_dir.glob(f"*{repo_name}*.json"))
            verifier_file = verifier_files[0] if verifier_files else None
        
        if verifier_file and verifier_file.exists():
            try:
                with open(verifier_file, 'r', encoding='utf-8') as f:
                    verifier_data = json.load(f)
                
                clarity_scores = []
                for comp_data in verifier_data.values():
                    if isinstance(comp_data, dict):
                        # Check for suggestion/reasoning in verifier output
                        suggestion = comp_data.get('suggestion', '')
                        if suggestion and len(suggestion) > 20:
                            clarity_scores.append(1.0)
                        elif suggestion:
                            clarity_scores.append(0.5)
                        else:
                            clarity_scores.append(0.0)
                
                if clarity_scores:
                    metrics.reasoning_clarity_score = sum(clarity_scores) / len(clarity_scores)
                    
            except Exception as e:
                self._log(f"Error analyzing explainability: {e}", "WARN")
        
        return metrics
    
    def _calculate_transparency(
        self,
        repo_name: str,
        executions: List[AgentExecution]
    ) -> TransparencyMetrics:
        """Calculate reasoning transparency metrics."""
        metrics = TransparencyMetrics()
        
        # Analyze execution flow for traceability
        component_flows = self.log_parser.get_all_component_flows(limit=100, repo_id=repo_name)
        
        for flow in component_flows:
            metrics.total_decisions += 1
            
            agents_involved = flow.get('agents_involved', [])
            executions_count = flow.get('total_executions', 0)
            
            # Check transparency: all expected agents involved
            expected_agents = {'reader', 'searcher', 'writer', 'verifier'}
            involved_set = set(agents_involved)
            
            if expected_agents.issubset(involved_set):
                metrics.transparent_decisions += 1
                metrics.traceable_steps += executions_count
            elif len(involved_set) >= 2:
                # Partially transparent
                metrics.transparent_decisions += 0.5
                metrics.traceable_steps += executions_count // 2
            else:
                metrics.opaque_decisions += 1
        
        # Calculate metrics
        metrics.transparency_score = metrics.transparent_decisions / max(metrics.total_decisions, 1)
        metrics.traceability_rate = metrics.traceable_steps / max(len(executions), 1)
        
        # Reasoning depth (number of agents per decision)
        if component_flows:
            total_agents = sum(len(f.get('agents_involved', [])) for f in component_flows)
            metrics.reasoning_depth_avg = total_agents / len(component_flows)
        
        return metrics
    
    # =========================================================================
    # Main Evaluation Methods
    # =========================================================================
    
    def evaluate_repository(
        self,
        repo_name: str,
        run_pipeline: bool = False
    ) -> AgentPerformanceReport:
        """
        Evaluate agent performance for a single repository.
        
        Args:
            repo_name: Repository name or path
            run_pipeline: Whether to run the pipeline first
        """
        self._log(f"\n{'='*60}")
        self._log(f"Evaluating: {repo_name}")
        self._log(f"{'='*60}")
        
        # Extract repo name from path if needed
        if os.path.sep in repo_name or '/' in repo_name:
            repo_name = Path(repo_name).name
        
        report = AgentPerformanceReport(
            repo_name=repo_name,
            evaluation_timestamp=datetime.now().isoformat(),
            total_components=0
        )
        
        try:
            # Run pipeline if requested
            if run_pipeline:
                self._log("Running pipeline...")
                from backend.pipeline import run_pipeline
                repo_path = DATA_ROOT / "input" / "repositories" / repo_name
                if not repo_path.exists():
                    repo_path = repo_name  # Try as direct path
                result = run_pipeline(str(repo_path))
                report.total_components = result.get('statistics', {}).get('total_processed', 0)
            
            # Load execution logs
            self._log("Loading execution logs...")
            executions_by_agent = self.log_parser.parse_orchestrator_logs(repo_id=repo_name)
            
            # Flatten executions for analysis
            all_executions = []
            for agent_execs in executions_by_agent.values():
                all_executions.extend(agent_execs)
            
            all_executions.sort(key=lambda e: e.timestamp)
            
            self._log(f"Found {len(all_executions)} execution records")
            
            # Calculate all metrics
            self._log("Calculating learning curve metrics...")
            report.learning_curve = self._calculate_learning_curve(repo_name, all_executions)
            
            self._log("Calculating error rate metrics...")
            report.error_rate = self._calculate_error_rate(repo_name, all_executions)
            
            self._log("Calculating hallucination metrics...")
            report.hallucination = self._calculate_hallucination_rate(repo_name)
            
            self._log("Calculating misalignment metrics...")
            report.misalignment = self._calculate_misalignment(repo_name, all_executions)
            
            self._log("Calculating collaboration metrics...")
            report.collaboration = self._calculate_collaboration(repo_name, all_executions)
            
            self._log("Calculating latency metrics...")
            report.latency = self._calculate_latency(repo_name, all_executions)
            
            self._log("Calculating instruction following metrics...")
            report.instruction_following = self._calculate_instruction_following(repo_name, all_executions)
            
            self._log("Calculating explainability metrics...")
            report.explainability = self._calculate_explainability(repo_name, all_executions)
            
            self._log("Calculating transparency metrics...")
            report.transparency = self._calculate_transparency(repo_name, all_executions)
            
            # Calculate overall score
            report.overall_score = self._calculate_overall_score(report)
            report.grade = self._assign_grade(report.overall_score)
            
            # Generate recommendations
            report.recommendations = self._generate_recommendations(report)
            
        except Exception as e:
            self._log(f"Error evaluating {repo_name}: {e}", "ERROR")
            traceback.print_exc()
            report.recommendations.append(f"Evaluation error: {str(e)}")
        
        self.reports.append(report)
        return report
    
    def _calculate_overall_score(self, report: AgentPerformanceReport) -> float:
        """Calculate weighted overall score from all metrics."""
        weights = {
            'learning': 0.10,
            'error_rate': 0.15,
            'hallucination': 0.15,
            'misalignment': 0.10,
            'collaboration': 0.15,
            'latency': 0.05,
            'instruction': 0.15,
            'explainability': 0.10,
            'transparency': 0.05
        }
        
        scores = {
            'learning': report.learning_curve.final_quality if report.learning_curve.final_quality else 0.5,
            'error_rate': 1.0 - report.error_rate.critical_error_rate,
            'hallucination': 1.0 - report.hallucination.hallucination_rate,
            'misalignment': 1.0 - report.misalignment.misalignment_rate,
            'collaboration': report.collaboration.collaboration_score,
            'latency': min(1.0, 1000 / max(report.latency.average_latency_ms, 1)),  # Lower latency = better
            'instruction': report.instruction_following.accuracy_rate,
            'explainability': report.explainability.justification_score,
            'transparency': report.transparency.transparency_score
        }
        
        overall = sum(weights[k] * scores[k] for k in weights)
        return round(overall, 3)
    
    def _assign_grade(self, score: float) -> str:
        """Assign letter grade based on score."""
        if score >= 0.9:
            return "A+"
        elif score >= 0.85:
            return "A"
        elif score >= 0.8:
            return "A-"
        elif score >= 0.75:
            return "B+"
        elif score >= 0.7:
            return "B"
        elif score >= 0.65:
            return "B-"
        elif score >= 0.6:
            return "C+"
        elif score >= 0.55:
            return "C"
        elif score >= 0.5:
            return "C-"
        elif score >= 0.4:
            return "D"
        else:
            return "F"
    
    def _generate_recommendations(self, report: AgentPerformanceReport) -> List[str]:
        """Generate actionable recommendations based on metrics."""
        recommendations = []
        
        # Learning curve recommendations
        if report.learning_curve.trend == "declining":
            recommendations.append("⚠️ Documentation quality is declining. Review recent changes to prompts or model configuration.")
        
        # Error rate recommendations
        if report.error_rate.critical_error_rate > 0.05:
            recommendations.append(f"🔴 High critical error rate ({report.error_rate.critical_error_rate:.1%}). Investigate error logs and add error handling.")
        
        if report.error_rate.tool_failure_rate > 0.1:
            recommendations.append(f"⚠️ High tool failure rate ({report.error_rate.tool_failure_rate:.1%}). Check LLM connection and model availability.")
        
        # Hallucination recommendations
        if report.hallucination.hallucination_rate > 0.1:
            recommendations.append(f"🔴 High hallucination rate ({report.hallucination.hallucination_rate:.1%}). Consider using more grounded prompts or RAG.")
        
        # Misalignment recommendations
        if report.misalignment.misalignment_rate > 0.15:
            recommendations.append(f"⚠️ High misalignment rate ({report.misalignment.misalignment_rate:.1%}). Review and clarify agent instructions.")
        
        # Collaboration recommendations
        if report.collaboration.collaboration_score < 0.7:
            recommendations.append("⚠️ Low collaboration score. Improve context passing between agents.")
        
        if report.collaboration.verifier_rejection_rate > 0.3:
            recommendations.append(f"📝 High verifier rejection rate ({report.collaboration.verifier_rejection_rate:.1%}). Writer agent may need prompt tuning.")
        
        # Latency recommendations
        if report.latency.average_latency_ms > 5000:
            recommendations.append(f"⏱️ High average latency ({report.latency.average_latency_ms:.0f}ms). Consider using a faster model or optimizing batch size.")
        
        # Instruction following recommendations
        if report.instruction_following.accuracy_rate < 0.7:
            recommendations.append(f"📋 Low instruction following ({report.instruction_following.accuracy_rate:.1%}). Make prompts more explicit.")
        
        # Explainability recommendations
        if report.explainability.justification_score < 0.5:
            recommendations.append("💡 Low explainability. Add reasoning requirements to agent prompts.")
        
        # Transparency recommendations
        if report.transparency.transparency_score < 0.6:
            recommendations.append("👁️ Low transparency. Ensure all agents log their decisions clearly.")
        
        if not recommendations:
            recommendations.append("✅ All metrics are within acceptable ranges. No immediate action required.")
        
        return recommendations
    
    def evaluate_multiple(
        self,
        repo_sources: List[str],
        run_pipeline: bool = False
    ) -> List[AgentPerformanceReport]:
        """
        Evaluate multiple repositories sequentially.
        
        Args:
            repo_sources: List of repository names/paths
            run_pipeline: Whether to run pipeline for each
        """
        self._log(f"\n{'='*80}")
        self._log("AGENT PERFORMANCE EVALUATION")
        self._log(f"Repositories: {len(repo_sources)}")
        self._log(f"{'='*80}\n")
        
        reports = []
        
        for i, repo in enumerate(repo_sources):
            self._log(f"\n[{i+1}/{len(repo_sources)}] Evaluating: {repo}")
            
            try:
                report = self.evaluate_repository(repo, run_pipeline=run_pipeline)
                reports.append(report)
                
                # Save individual report
                self._save_individual_report(report)
                
            except Exception as e:
                self._log(f"Failed to evaluate {repo}: {e}", "ERROR")
        
        # Generate combined summary
        self._generate_combined_summary(reports)
        
        return reports
    
    def _save_individual_report(self, report: AgentPerformanceReport):
        """Save individual repository report."""
        repo_dir = self.output_dir / report.repo_name
        repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON report
        json_file = repo_dir / "performance_report.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(report), f, indent=2, default=str)
        
        self._log(f"Saved report to: {json_file}")
    
    def _generate_combined_summary(self, reports: List[AgentPerformanceReport]):
        """Generate combined summary of all evaluations."""
        if not reports:
            return
        
        summary = {
            "evaluation_timestamp": self.timestamp,
            "total_repositories": len(reports),
            "reports": [asdict(r) for r in reports],
            "aggregate_metrics": {
                "average_overall_score": sum(r.overall_score for r in reports) / len(reports),
                "average_error_rate": sum(r.error_rate.critical_error_rate for r in reports) / len(reports),
                "average_hallucination_rate": sum(r.hallucination.hallucination_rate for r in reports) / len(reports),
                "average_collaboration_score": sum(r.collaboration.collaboration_score for r in reports) / len(reports),
                "average_instruction_accuracy": sum(r.instruction_following.accuracy_rate for r in reports) / len(reports),
            },
            "grade_distribution": {},
            "all_recommendations": []
        }
        
        # Grade distribution
        for report in reports:
            grade = report.grade
            summary["grade_distribution"][grade] = summary["grade_distribution"].get(grade, 0) + 1
        
        # Collect all unique recommendations
        all_recs = set()
        for report in reports:
            all_recs.update(report.recommendations)
        summary["all_recommendations"] = list(all_recs)
        
        # Save summary JSON
        summary_file = self.output_dir / "evaluation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, default=str)
        
        # Generate markdown report
        self._generate_markdown_summary(summary, reports)
        
        self._log(f"\nSummary saved to: {summary_file}")
    
    def _generate_markdown_summary(
        self,
        summary: Dict[str, Any],
        reports: List[AgentPerformanceReport]
    ):
        """Generate human-readable markdown summary."""
        md = f"""# Agent Performance Evaluation Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Repositories Evaluated:** {summary['total_repositories']}
**Output Directory:** `{self.output_dir}`

---

## Executive Summary

| Metric | Average |
|--------|---------|
| Overall Score | {summary['aggregate_metrics']['average_overall_score']:.1%} |
| Error Rate | {summary['aggregate_metrics']['average_error_rate']:.1%} |
| Hallucination Rate | {summary['aggregate_metrics']['average_hallucination_rate']:.1%} |
| Collaboration Score | {summary['aggregate_metrics']['average_collaboration_score']:.1%} |
| Instruction Accuracy | {summary['aggregate_metrics']['average_instruction_accuracy']:.1%} |

### Grade Distribution

"""
        for grade, count in sorted(summary['grade_distribution'].items()):
            md += f"- **{grade}**: {count} repository(s)\n"
        
        md += "\n---\n\n## Repository Details\n\n"
        
        for report in reports:
            md += f"""### {report.repo_name}

- **Overall Score:** {report.overall_score:.1%} ({report.grade})
- **Components Evaluated:** {report.total_components}

| Metric Category | Key Metric | Value |
|-----------------|------------|-------|
| Learning Curve | Improvement Rate | {report.learning_curve.improvement_rate:+.1%} |
| Error Rate | Critical Errors | {report.error_rate.critical_error_rate:.1%} |
| Hallucination | Rate | {report.hallucination.hallucination_rate:.1%} |
| Misalignment | Rate | {report.misalignment.misalignment_rate:.1%} |
| Collaboration | Score | {report.collaboration.collaboration_score:.1%} |
| Latency | Avg (ms) | {report.latency.average_latency_ms:.0f} |
| Instruction Following | Accuracy | {report.instruction_following.accuracy_rate:.1%} |
| Explainability | Score | {report.explainability.justification_score:.1%} |
| Transparency | Score | {report.transparency.transparency_score:.1%} |

**Recommendations:**
"""
            for rec in report.recommendations:
                md += f"- {rec}\n"
            
            md += "\n---\n\n"
        
        md += """## Metrics Definitions

1. **Learning Curve (Improvement Rate)**: Measures how documentation quality improves across iterations
2. **Critical Error Rate**: Percentage of executions resulting in critical/unrecoverable errors
3. **Hallucination Rate**: Percentage of mentioned components that don't actually exist
4. **Misalignment Rate**: Percentage of outputs that deviate from instructions
5. **Collaboration Score**: Quality of inter-agent handoffs and context sharing
6. **Response Latency**: Average time between agent executions
7. **Instruction Following Accuracy**: How well agents follow their prompts
8. **Explainability Score**: Percentage of actions with clear justifications
9. **Transparency Score**: Traceability of agent decision-making process

---

*Report generated by Code_IQ Agent Performance Evaluator*
"""
        
        md_file = self.output_dir / "evaluation_report.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md)
        
        self._log(f"Markdown report saved to: {md_file}")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Code_IQ agent pipeline performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Evaluate existing outputs for multiple repos
    python scripts/evaluate_agent_performance.py --repos repo1,repo2,repo3
    
    # Evaluate a single repository
    python scripts/evaluate_agent_performance.py --repos my-repo
    
    # Run pipeline first, then evaluate
    python scripts/evaluate_agent_performance.py --repos my-repo --run-pipeline
    
    # Use existing evaluation data
    python scripts/evaluate_agent_performance.py --repos my-repo --use-existing
        """
    )
    
    parser.add_argument(
        "--repos",
        required=True,
        help="Comma-separated list of repository names/paths to evaluate"
    )
    
    parser.add_argument(
        "--run-pipeline",
        action="store_true",
        help="Run the documentation pipeline before evaluation"
    )
    
    parser.add_argument(
        "--use-existing",
        action="store_true",
        help="Use existing pipeline outputs (don't run pipeline)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Custom output directory"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    args = parser.parse_args()
    
    # Parse repository list
    repos = [r.strip() for r in args.repos.split(',') if r.strip()]
    
    if not repos:
        print("Error: No repositories specified")
        sys.exit(1)
    
    print("\n" + "="*80)
    print("CODE_IQ AGENT PERFORMANCE EVALUATOR")
    print("="*80)
    print(f"Repositories: {', '.join(repos)}")
    print(f"Run Pipeline: {args.run_pipeline}")
    print("="*80 + "\n")
    
    evaluator = AgentPerformanceEvaluator(
        output_dir=args.output_dir,
        verbose=not args.quiet
    )
    
    try:
        reports = evaluator.evaluate_multiple(
            repo_sources=repos,
            run_pipeline=args.run_pipeline
        )
        
        print("\n" + "="*80)
        print("EVALUATION COMPLETE")
        print("="*80)
        
        for report in reports:
            print(f"\n{report.repo_name}: {report.overall_score:.1%} ({report.grade})")
        
        print(f"\nResults saved to: {evaluator.output_dir}")
        print("="*80 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nEvaluation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nEvaluation failed: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
