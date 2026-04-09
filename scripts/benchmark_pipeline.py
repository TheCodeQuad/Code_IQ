#!/usr/bin/env python3
"""
Benchmark Pipeline Script
=========================

This script runs the Code_IQ documentation generation pipeline with different:
1. LLM models - Compare performance across various model configurations
2. Graph inputs - Test pipeline with DAG, CFG, HPG, PDG representations

Usage:
    # Run with different LLM models
    python scripts/benchmark_pipeline.py --mode models --repo <github_url_or_local_path>

    # Run with different graph inputs
    python scripts/benchmark_pipeline.py --mode graphs --repo <github_url_or_local_path>

    # Run both benchmarks
    python scripts/benchmark_pipeline.py --mode all --repo <github_url_or_local_path>

Output:
    - Documentation outputs saved to: data/benchmark_results/{timestamp}/{mode}/
    - Evaluation results saved alongside with proper naming
"""

import os
import sys
import json
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import traceback
import copy

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.paths import DATA_ROOT
from backend.utils.logger import get_logger
from backend.utils.config_handler import get_config, ConfigHandler
from backend.navigator.core.repo_loader import clone_repo, extract_repo_name

logger = get_logger(__name__)


class GraphType(Enum):
    """Types of graph representations for code analysis"""
    DAG = "dag"      # Dependency Acyclic Graph (default - AST-based)
    CFG = "cfg"      # Control Flow Graph
    HPG = "hpg"      # Hierarchical Program Graph
    PDG = "pdg"      # Program Dependency Graph


@dataclass
class BenchmarkConfig:
    """Configuration for a single benchmark run"""
    name: str
    description: str
    model_path: Optional[str] = None
    model_name: Optional[str] = None
    graph_type: Optional[GraphType] = None
    provider: str = "local"
    temperature: float = 0.3
    max_tokens: int = 2000
    n_ctx: int = 8192


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run"""
    config_name: str
    repo_name: str
    start_time: str
    end_time: str
    duration_seconds: float
    total_components: int
    successful_docs: int
    failed_docs: int
    success_rate: float
    evaluation_scores: Dict[str, Any]
    documentation_path: str
    evaluation_path: str
    error: Optional[str] = None


class BenchmarkPipeline:
    """
    Benchmark pipeline for testing documentation generation with
    different LLM models and graph representations.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        verbose: bool = True
    ):
        self.verbose = verbose
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Set up output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = DATA_ROOT / "benchmark_results" / self.timestamp
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Store original config for restoration
        self._original_config = None
        
        # Available models (local GGUF files)
        self.available_models = self._discover_models()
        
        self.results: List[BenchmarkResult] = []
        
    def _discover_models(self) -> Dict[str, Path]:
        """Discover available local models"""
        models_dir = PROJECT_ROOT / "models"
        available = {}
        
        if models_dir.exists():
            for model_file in models_dir.glob("*.gguf"):
                model_name = model_file.stem
                available[model_name] = model_file
                
        self._log(f"Discovered {len(available)} local models: {list(available.keys())}")
        return available
    
    def _log(self, message: str, level: str = "INFO"):
        """Log message to console and logger"""
        if self.verbose:
            print(f"[{level}] {message}")
        if level == "INFO":
            logger.info(message)
        elif level == "WARN":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
    
    def _prepare_repository(self, repo_source: str) -> str:
        """
        Prepare repository for analysis.
        Handles both GitHub URLs and local paths.
        """
        # Check if it's a local path
        if os.path.exists(repo_source):
            self._log(f"Using local repository: {repo_source}")
            return repo_source
        
        # Check if it's a GitHub URL
        if "github.com" in repo_source or repo_source.startswith("git@"):
            self._log(f"Cloning repository from: {repo_source}")
            repo_path = clone_repo(repo_source)
            self._log(f"Repository cloned to: {repo_path}")
            return repo_path
        
        # Check if it might be a repo name in data directory
        data_repo_path = DATA_ROOT / "input" / "repositories" / repo_source
        if data_repo_path.exists():
            self._log(f"Using existing repository: {data_repo_path}")
            return str(data_repo_path)
        
        raise ValueError(f"Repository not found: {repo_source}")
    
    def _backup_config(self):
        """Backup current configuration"""
        config_path = PROJECT_ROOT / "config" / "llm.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, 'r') as f:
                self._original_config = yaml.safe_load(f)
    
    def _restore_config(self):
        """Restore original configuration"""
        if self._original_config:
            config_path = PROJECT_ROOT / "config" / "llm.yaml"
            import yaml
            with open(config_path, 'w') as f:
                yaml.dump(self._original_config, f, default_flow_style=False)
            self._log("Configuration restored to original state")
    
    def _apply_model_config(self, config: BenchmarkConfig):
        """Apply model configuration for benchmark run"""
        import yaml
        config_path = PROJECT_ROOT / "config" / "llm.yaml"
        
        with open(config_path, 'r') as f:
            llm_config = yaml.safe_load(f)
        
        # Update local model settings
        if config.model_path:
            llm_config['providers']['local']['model_path'] = config.model_path
        
        llm_config['providers']['local']['enabled'] = (config.provider == "local")
        
        if config.provider == "local":
            llm_config['providers']['local']['default_params']['temperature'] = config.temperature
            llm_config['providers']['local']['default_params']['max_tokens'] = config.max_tokens
            llm_config['providers']['local']['n_ctx'] = config.n_ctx
        
        # Update agent models if needed
        if config.model_name:
            for agent in ['reader', 'searcher', 'writer', 'verifier', 'evaluator']:
                if agent in llm_config.get('agent_models', {}):
                    llm_config['agent_models'][agent]['model'] = config.model_name
        
        with open(config_path, 'w') as f:
            yaml.dump(llm_config, f, default_flow_style=False)
        
        # Reset LLM client to pick up new config
        from backend.utils.llm_client import reset_llm_client
        reset_llm_client()
        
        self._log(f"Applied model config: {config.name}")
    
    def _run_pipeline(
        self,
        repo_path: str,
        config: BenchmarkConfig,
        output_subdir: str
    ) -> BenchmarkResult:
        """Run single pipeline iteration with given configuration"""
        repo_name = extract_repo_name(repo_path) if "://" in repo_path or "@" in repo_path else Path(repo_path).name
        start_time = datetime.now()
        
        # Create output directories
        run_output_dir = self.output_dir / output_subdir / config.name
        run_output_dir.mkdir(parents=True, exist_ok=True)
        
        doc_output_dir = run_output_dir / "documentation"
        eval_output_dir = run_output_dir / "evaluation"
        doc_output_dir.mkdir(parents=True, exist_ok=True)
        eval_output_dir.mkdir(parents=True, exist_ok=True)
        
        result = BenchmarkResult(
            config_name=config.name,
            repo_name=repo_name,
            start_time=start_time.isoformat(),
            end_time="",
            duration_seconds=0,
            total_components=0,
            successful_docs=0,
            failed_docs=0,
            success_rate=0,
            evaluation_scores={},
            documentation_path=str(doc_output_dir),
            evaluation_path=str(eval_output_dir),
        )
        
        try:
            self._log(f"\n{'='*60}")
            self._log(f"Running benchmark: {config.name}")
            self._log(f"Repository: {repo_name}")
            self._log(f"Graph type: {config.graph_type.value if config.graph_type else 'DAG (default)'}")
            self._log(f"{'='*60}")
            
            # Apply model configuration
            if config.model_path:
                self._apply_model_config(config)
            
            # Run the pipeline
            from backend.pipeline import run_pipeline
            
            pipeline_result = run_pipeline(repo_path)
            
            # Extract statistics
            stats = pipeline_result.get('statistics', {})
            result.total_components = stats.get('total_processed', 0)
            result.successful_docs = stats.get('successful', 0)
            result.failed_docs = stats.get('failed', 0)
            result.success_rate = stats.get('success_rate', 0)
            
            # Save documentation output
            docs = pipeline_result.get('documentation', [])
            doc_output_file = doc_output_dir / f"{repo_name}_documentation.json"
            
            serialized_docs = {}
            for doc in docs:
                if hasattr(doc, 'to_dict'):
                    serialized_docs[doc.component_id] = doc.to_dict()
                elif hasattr(doc, 'component_id'):
                    serialized_docs[doc.component_id] = {
                        'component_id': doc.component_id,
                        'docstring': getattr(doc, 'docstring', ''),
                        'quality_score': getattr(doc, 'quality_score', 0),
                    }
            
            with open(doc_output_file, 'w', encoding='utf-8') as f:
                json.dump(serialized_docs, f, indent=2, default=str)
            
            self._log(f"Documentation saved to: {doc_output_file}")
            
            # Run evaluation
            evaluation_scores = self._run_evaluation(repo_name, eval_output_dir, config)
            result.evaluation_scores = evaluation_scores
            
        except Exception as e:
            result.error = str(e)
            self._log(f"Pipeline error: {e}", "ERROR")
            traceback.print_exc()
        
        finally:
            end_time = datetime.now()
            result.end_time = end_time.isoformat()
            result.duration_seconds = (end_time - start_time).total_seconds()
            
            # Save individual result
            result_file = run_output_dir / "benchmark_result.json"
            with open(result_file, 'w') as f:
                json.dump(asdict(result), f, indent=2, default=str)
            
            self._log(f"Benchmark complete: {config.name}")
            self._log(f"Duration: {result.duration_seconds:.2f}s")
            self._log(f"Success rate: {result.success_rate:.1f}%")
        
        return result
    
    def _run_evaluation(
        self,
        repo_name: str,
        output_dir: Path,
        config: BenchmarkConfig
    ) -> Dict[str, Any]:
        """Run evaluation on generated documentation"""
        try:
            from backend.unified_evaluator import UnifiedEvaluator
            
            self._log(f"Running evaluation for {repo_name}...")
            
            evaluator = UnifiedEvaluator(repo_name=repo_name)
            results = evaluator.evaluate_all()
            
            # Build evaluation filename with config info
            graph_suffix = f"_{config.graph_type.value}" if config.graph_type else "_dag"
            model_suffix = f"_{config.name}" if config.name else ""
            
            eval_filename = f"evaluation{graph_suffix}{model_suffix}.json"
            eval_file = output_dir / eval_filename
            
            with open(eval_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            
            self._log(f"Evaluation saved to: {eval_file}")
            
            return {
                'overall_quality': results.get('overall_quality_score', 0),
                'completeness': results.get('completeness', {}).get('summary', {}).get('overall_score', 0),
                'helpfulness': results.get('helpfulness', {}).get('summary', {}).get('average_score', 0),
                'truthfulness': results.get('truthfulness', {}).get('summary', {}).get('overall_accuracy', 0),
            }
            
        except Exception as e:
            self._log(f"Evaluation error: {e}", "WARN")
            return {'error': str(e)}
    
    def get_model_benchmark_configs(self) -> List[BenchmarkConfig]:
        """Generate benchmark configurations for different models"""
        configs = []
        
        # Use only CodeLlama 13B Instruct model
        target_model = "codellama-13b-instruct.Q4_K_M"
        
        if target_model in self.available_models:
            model_path = self.available_models[target_model]
            configs.append(BenchmarkConfig(
                name=target_model,
                description=f"Benchmark with {target_model}",
                model_path=str(model_path),
                model_name=target_model,
                provider="local",
                temperature=0.3,
                max_tokens=2000,
                n_ctx=8192,
            ))
            self._log(f"Selected model: {target_model}")
        else:
            # If target model not found, try any available model
            if self.available_models:
                model_name = list(self.available_models.keys())[0]
                model_path = self.available_models[model_name]
                self._log(f"Target model {target_model} not found. Using available model: {model_name}", "WARN")
                configs.append(BenchmarkConfig(
                    name=model_name,
                    description=f"Benchmark with {model_name}",
                    model_path=str(model_path),
                    model_name=model_name,
                    provider="local",
                    temperature=0.3,
                    max_tokens=2000,
                    n_ctx=8192,
                ))
            else:
                self._log(f"Model {target_model} not found and no other models available.", "ERROR")
        
        return configs
    
    def get_graph_benchmark_configs(self) -> List[BenchmarkConfig]:
        """Generate benchmark configurations for different graph types"""
        # Use the first available model for graph benchmarks
        model_path = None
        model_name = None
        
        if self.available_models:
            model_name = list(self.available_models.keys())[0]
            model_path = str(self.available_models[model_name])
        
        configs = []
        
        for graph_type in GraphType:
            configs.append(BenchmarkConfig(
                name=f"graph_{graph_type.value}",
                description=f"Benchmark with {graph_type.value.upper()} graph representation",
                model_path=model_path,
                model_name=model_name,
                graph_type=graph_type,
                provider="local",
                temperature=0.3,
                max_tokens=2000,
                n_ctx=8192,
            ))
        
        return configs
    
    def _apply_graph_config(self, config: BenchmarkConfig, repo_path: str):
        """
        Apply graph configuration by generating the appropriate graph type.
        This modifies how the pipeline processes the repository.
        """
        if not config.graph_type or config.graph_type == GraphType.DAG:
            # DAG is the default, no special handling needed
            return
        
        graph_type = config.graph_type
        self._log(f"Generating {graph_type.value.upper()} representation...")
        
        # Create graph output directory
        graph_output_dir = self.output_dir / "graphs" / config.name
        graph_output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if graph_type == GraphType.CFG:
                self._generate_cfg(repo_path, graph_output_dir)
            elif graph_type == GraphType.HPG:
                self._generate_hpg(repo_path, graph_output_dir)
            elif graph_type == GraphType.PDG:
                self._generate_pdg(repo_path, graph_output_dir)
                
        except Exception as e:
            self._log(f"Graph generation warning for {graph_type.value}: {e}", "WARN")
    
    def _generate_cfg(self, repo_path: str, output_dir: Path):
        """
        Generate Control Flow Graph representation.
        CFG captures the flow of control between statements.
        """
        from backend.navigator.core.repository_parser import RepositoryParser
        from backend.navigator.core.topo import build_graph_from_components
        import networkx as nx
        
        parser = RepositoryParser(repo_path)
        components = parser.parse()
        
        cfg_data = {}
        
        for comp_id, comp in components.items():
            # Extract control flow from source code
            source = getattr(comp, 'source_code', '') or ''
            
            # Basic CFG extraction from control flow keywords
            cfg_nodes = []
            cfg_edges = []
            
            lines = source.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                # Identify control flow nodes
                if any(kw in stripped for kw in ['if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except', 'finally:', 'with ', 'match ', 'case ']):
                    cfg_nodes.append({
                        'id': f"{comp_id}_line_{i}",
                        'line': i,
                        'type': 'control',
                        'content': stripped[:50]
                    })
                elif stripped and not stripped.startswith('#'):
                    cfg_nodes.append({
                        'id': f"{comp_id}_line_{i}",
                        'line': i,
                        'type': 'statement',
                        'content': stripped[:50]
                    })
            
            # Build sequential edges
            for i in range(len(cfg_nodes) - 1):
                cfg_edges.append({
                    'from': cfg_nodes[i]['id'],
                    'to': cfg_nodes[i + 1]['id'],
                    'type': 'sequential'
                })
            
            cfg_data[comp_id] = {
                'component_id': comp_id,
                'nodes': cfg_nodes,
                'edges': cfg_edges,
                'node_count': len(cfg_nodes),
                'edge_count': len(cfg_edges)
            }
        
        # Save CFG data
        cfg_file = output_dir / "cfg_graph.json"
        with open(cfg_file, 'w') as f:
            json.dump(cfg_data, f, indent=2)
        
        self._log(f"CFG generated with {len(cfg_data)} components")
        
        # Store for pipeline use
        self._current_graph_data = cfg_data
        self._current_graph_type = GraphType.CFG
    
    def _generate_hpg(self, repo_path: str, output_dir: Path):
        """
        Generate Hierarchical Program Graph representation.
        HPG captures hierarchical relationships between code elements.
        """
        from backend.navigator.core.repository_parser import RepositoryParser
        
        parser = RepositoryParser(repo_path)
        components = parser.parse()
        
        hpg_data = {
            'modules': {},
            'classes': {},
            'functions': {},
            'hierarchy': []
        }
        
        # Build hierarchy
        for comp_id, comp in components.items():
            comp_type = str(getattr(comp, 'type', 'unknown'))
            
            node = {
                'id': comp_id,
                'name': getattr(comp, 'name', comp_id),
                'type': comp_type,
                'children': [],
                'parent': None
            }
            
            if 'MODULE' in comp_type.upper():
                hpg_data['modules'][comp_id] = node
            elif 'CLASS' in comp_type.upper():
                hpg_data['classes'][comp_id] = node
                # Link to parent module if available
                module_path = getattr(getattr(comp, 'location', None), 'file_path', '')
                if module_path:
                    for mod_id in hpg_data['modules']:
                        if mod_id in module_path or module_path in mod_id:
                            node['parent'] = mod_id
                            hpg_data['modules'][mod_id]['children'].append(comp_id)
                            break
            else:
                hpg_data['functions'][comp_id] = node
                # Link to parent class/module
                parent_classes = getattr(comp, 'parent_classes', [])
                if parent_classes:
                    for parent_class in parent_classes:
                        if parent_class in hpg_data['classes']:
                            node['parent'] = parent_class
                            hpg_data['classes'][parent_class]['children'].append(comp_id)
                            break
        
        # Build hierarchy edges
        for category in ['modules', 'classes', 'functions']:
            for node_id, node in hpg_data[category].items():
                if node['parent']:
                    hpg_data['hierarchy'].append({
                        'parent': node['parent'],
                        'child': node_id,
                        'relationship': 'contains'
                    })
        
        # Save HPG data
        hpg_file = output_dir / "hpg_graph.json"
        with open(hpg_file, 'w') as f:
            json.dump(hpg_data, f, indent=2)
        
        self._log(f"HPG generated: {len(hpg_data['modules'])} modules, {len(hpg_data['classes'])} classes, {len(hpg_data['functions'])} functions")
        
        self._current_graph_data = hpg_data
        self._current_graph_type = GraphType.HPG
    
    def _generate_pdg(self, repo_path: str, output_dir: Path):
        """
        Generate Program Dependency Graph representation.
        PDG captures both data and control dependencies.
        """
        from backend.navigator.core.repository_parser import RepositoryParser
        from backend.navigator.core.topo import build_graph_from_components
        
        parser = RepositoryParser(repo_path)
        components = parser.parse()
        
        # Build basic dependency graph
        dep_graph = build_graph_from_components(components)
        
        pdg_data = {
            'nodes': {},
            'data_dependencies': [],
            'control_dependencies': [],
            'call_dependencies': []
        }
        
        for comp_id, comp in components.items():
            source = getattr(comp, 'source_code', '') or ''
            
            # Extract variable definitions and uses
            var_defs = set()
            var_uses = set()
            
            import re
            # Simple variable definition detection
            def_pattern = r'\b(\w+)\s*='
            use_pattern = r'\b(\w+)\b'
            
            for match in re.finditer(def_pattern, source):
                var_defs.add(match.group(1))
            
            for match in re.finditer(use_pattern, source):
                var = match.group(1)
                if var not in var_defs and not var[0].isupper():  # Exclude classes
                    var_uses.add(var)
            
            pdg_data['nodes'][comp_id] = {
                'id': comp_id,
                'name': getattr(comp, 'name', comp_id),
                'defines': list(var_defs),
                'uses': list(var_uses),
                'calls': getattr(comp, 'calls', []),
                'depends_on': getattr(comp, 'depends_on', [])
            }
            
            # Build data dependencies
            for dep_id in getattr(comp, 'depends_on', []):
                if dep_id in components:
                    dep_comp = components[dep_id]
                    # Check if there's a variable flow
                    dep_source = getattr(dep_comp, 'source_code', '') or ''
                    for var in var_uses:
                        if var in dep_source:
                            pdg_data['data_dependencies'].append({
                                'from': dep_id,
                                'to': comp_id,
                                'variable': var,
                                'type': 'data_flow'
                            })
            
            # Build call dependencies
            for call in getattr(comp, 'calls', []):
                if call in components:
                    pdg_data['call_dependencies'].append({
                        'caller': comp_id,
                        'callee': call,
                        'type': 'call'
                    })
        
        # Save PDG data
        pdg_file = output_dir / "pdg_graph.json"
        with open(pdg_file, 'w') as f:
            json.dump(pdg_data, f, indent=2)
        
        self._log(f"PDG generated: {len(pdg_data['nodes'])} nodes, {len(pdg_data['data_dependencies'])} data deps, {len(pdg_data['call_dependencies'])} call deps")
        
        self._current_graph_data = pdg_data
        self._current_graph_type = GraphType.PDG
    
    def run_model_benchmarks(self, repo_source: str) -> List[BenchmarkResult]:
        """Run benchmarks with different LLM models"""
        self._log("\n" + "="*80)
        self._log("STARTING MODEL BENCHMARKS")
        self._log("="*80)
        
        repo_path = self._prepare_repository(repo_source)
        configs = self.get_model_benchmark_configs()
        
        if not configs:
            self._log("No model configurations available", "ERROR")
            return []
        
        self._backup_config()
        
        results = []
        try:
            for i, config in enumerate(configs):
                self._log(f"\n[{i+1}/{len(configs)}] Running model benchmark: {config.name}")
                
                result = self._run_pipeline(
                    repo_path=repo_path,
                    config=config,
                    output_subdir="models"
                )
                results.append(result)
                self.results.append(result)
                
        finally:
            self._restore_config()
        
        return results
    
    def run_graph_benchmarks(self, repo_source: str) -> List[BenchmarkResult]:
        """Run benchmarks with different graph representations"""
        self._log("\n" + "="*80)
        self._log("STARTING GRAPH BENCHMARKS")
        self._log("="*80)
        
        repo_path = self._prepare_repository(repo_source)
        configs = self.get_graph_benchmark_configs()
        
        self._backup_config()
        
        results = []
        try:
            for i, config in enumerate(configs):
                self._log(f"\n[{i+1}/{len(configs)}] Running graph benchmark: {config.name}")
                
                # Generate graph representation
                self._apply_graph_config(config, repo_path)
                
                # Apply model config
                if config.model_path:
                    self._apply_model_config(config)
                
                result = self._run_pipeline(
                    repo_path=repo_path,
                    config=config,
                    output_subdir="graphs"
                )
                results.append(result)
                self.results.append(result)
                
        finally:
            self._restore_config()
        
        return results
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate summary report of all benchmark results"""
        if not self.results:
            return {"error": "No benchmark results available"}
        
        # Group by benchmark type
        model_results = [r for r in self.results if "graph_" not in r.config_name]
        graph_results = [r for r in self.results if "graph_" in r.config_name]
        
        summary = {
            "timestamp": self.timestamp,
            "output_directory": str(self.output_dir),
            "total_benchmarks": len(self.results),
            "model_benchmarks": {
                "count": len(model_results),
                "results": [asdict(r) for r in model_results],
                "best_model": None,
                "comparison": {}
            },
            "graph_benchmarks": {
                "count": len(graph_results),
                "results": [asdict(r) for r in graph_results],
                "best_graph": None,
                "comparison": {}
            }
        }
        
        # Find best model
        if model_results:
            valid_results = [r for r in model_results if not r.error]
            if valid_results:
                best = max(valid_results, key=lambda r: r.evaluation_scores.get('overall_quality', 0))
                summary["model_benchmarks"]["best_model"] = {
                    "name": best.config_name,
                    "overall_quality": best.evaluation_scores.get('overall_quality', 0),
                    "success_rate": best.success_rate,
                    "duration": best.duration_seconds
                }
                
                # Build comparison table
                summary["model_benchmarks"]["comparison"] = {
                    r.config_name: {
                        "overall_quality": r.evaluation_scores.get('overall_quality', 0),
                        "completeness": r.evaluation_scores.get('completeness', 0),
                        "helpfulness": r.evaluation_scores.get('helpfulness', 0),
                        "truthfulness": r.evaluation_scores.get('truthfulness', 0),
                        "success_rate": r.success_rate,
                        "duration": r.duration_seconds
                    }
                    for r in valid_results
                }
        
        # Find best graph type
        if graph_results:
            valid_results = [r for r in graph_results if not r.error]
            if valid_results:
                best = max(valid_results, key=lambda r: r.evaluation_scores.get('overall_quality', 0))
                summary["graph_benchmarks"]["best_graph"] = {
                    "name": best.config_name,
                    "overall_quality": best.evaluation_scores.get('overall_quality', 0),
                    "success_rate": best.success_rate,
                    "duration": best.duration_seconds
                }
                
                # Build comparison table
                summary["graph_benchmarks"]["comparison"] = {
                    r.config_name: {
                        "overall_quality": r.evaluation_scores.get('overall_quality', 0),
                        "completeness": r.evaluation_scores.get('completeness', 0),
                        "helpfulness": r.evaluation_scores.get('helpfulness', 0),
                        "truthfulness": r.evaluation_scores.get('truthfulness', 0),
                        "success_rate": r.success_rate,
                        "duration": r.duration_seconds
                    }
                    for r in valid_results
                }
        
        # Save summary
        summary_file = self.output_dir / "benchmark_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        # Generate markdown report
        self._generate_markdown_report(summary)
        
        return summary
    
    def _generate_markdown_report(self, summary: Dict[str, Any]):
        """Generate a human-readable markdown report"""
        report = f"""# Code_IQ Benchmark Report

Generated: {summary['timestamp']}
Output Directory: `{summary['output_directory']}`
Total Benchmarks: {summary['total_benchmarks']}

---

## Model Benchmarks

"""
        
        model_benchmarks = summary.get('model_benchmarks', {})
        if model_benchmarks.get('count', 0) > 0:
            best = model_benchmarks.get('best_model')
            if best:
                report += f"""### Best Performing Model
- **Model:** {best['name']}
- **Overall Quality:** {best['overall_quality']:.1%}
- **Success Rate:** {best['success_rate']:.1f}%
- **Duration:** {best['duration']:.2f}s

### Comparison

| Model | Quality | Completeness | Helpfulness | Truthfulness | Success Rate | Duration |
|-------|---------|--------------|-------------|--------------|--------------|----------|
"""
                for name, scores in model_benchmarks.get('comparison', {}).items():
                    report += f"| {name} | {scores['overall_quality']:.1%} | {scores['completeness']:.1%} | {scores['helpfulness']:.1%} | {scores['truthfulness']:.1%} | {scores['success_rate']:.1f}% | {scores['duration']:.1f}s |\n"
        else:
            report += "*No model benchmarks run*\n"
        
        report += "\n---\n\n## Graph Benchmarks\n\n"
        
        graph_benchmarks = summary.get('graph_benchmarks', {})
        if graph_benchmarks.get('count', 0) > 0:
            best = graph_benchmarks.get('best_graph')
            if best:
                report += f"""### Best Performing Graph Type
- **Graph Type:** {best['name'].replace('graph_', '').upper()}
- **Overall Quality:** {best['overall_quality']:.1%}
- **Success Rate:** {best['success_rate']:.1f}%
- **Duration:** {best['duration']:.2f}s

### Comparison

| Graph Type | Quality | Completeness | Helpfulness | Truthfulness | Success Rate | Duration |
|------------|---------|--------------|-------------|--------------|--------------|----------|
"""
                for name, scores in graph_benchmarks.get('comparison', {}).items():
                    graph_name = name.replace('graph_', '').upper()
                    report += f"| {graph_name} | {scores['overall_quality']:.1%} | {scores['completeness']:.1%} | {scores['helpfulness']:.1%} | {scores['truthfulness']:.1%} | {scores['success_rate']:.1f}% | {scores['duration']:.1f}s |\n"
        else:
            report += "*No graph benchmarks run*\n"
        
        report += f"""
---

## Files Generated

- Summary: `benchmark_summary.json`
- This report: `benchmark_report.md`
- Model results: `models/*/`
- Graph results: `graphs/*/`

## Notes

- **DAG**: Dependency Acyclic Graph (default AST-based representation)
- **CFG**: Control Flow Graph (captures control flow between statements)
- **HPG**: Hierarchical Program Graph (captures structural hierarchy)
- **PDG**: Program Dependency Graph (captures data and control dependencies)
"""
        
        report_file = self.output_dir / "benchmark_report.md"
        with open(report_file, 'w') as f:
            f.write(report)
        
        self._log(f"Markdown report saved to: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Code_IQ pipeline with different models and graph types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run model benchmarks on single repo
    python scripts/benchmark_pipeline.py --mode models --repo https://github.com/user/repo
    
    # Run graph benchmarks on multiple repos
    python scripts/benchmark_pipeline.py --mode graphs --repo ./local/repo1 ./local/repo2 ./local/repo3
    
    # Run all benchmarks on multiple repos (mixed sources)
    python scripts/benchmark_pipeline.py --mode all --repo https://github.com/user/repo1 ./local/repo2 my-repo-name
    
    # Run on single local repo
    python scripts/benchmark_pipeline.py --mode all --repo my-cloned-repo
        """
    )
    
    parser.add_argument(
        "--repo",
        required=True,
        nargs="+",
        help="Repository source(s): GitHub URL(s), local path(s), or name(s) of existing repos. Accepts multiple repos separated by spaces."
    )
    
    parser.add_argument(
        "--mode",
        choices=["models", "graphs", "all"],
        default="all",
        help="Benchmark mode: 'models' for LLM comparison, 'graphs' for graph type comparison, 'all' for both"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Custom output directory (default: data/benchmark_results/{timestamp})"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("CODE_IQ BENCHMARK PIPELINE")
    print("="*80)
    print(f"Repository: {args.repo}")
    print(f"Mode: {args.mode}")
    print("="*80 + "\n")
    
    benchmark = BenchmarkPipeline(
        output_dir=args.output_dir,
        verbose=not args.quiet
    )
    
    # Ensure repos is a list (in case single repo is passed)
    repos = args.repo if isinstance(args.repo, list) else [args.repo]
    
    try:
        for repo_idx, repo_source in enumerate(repos, 1):
            print(f"\n[{repo_idx}/{len(repos)}] Processing repository: {repo_source}")
            
            if args.mode in ["models", "all"]:
                benchmark.run_model_benchmarks(repo_source)
            
            if args.mode in ["graphs", "all"]:
                benchmark.run_graph_benchmarks(repo_source)
        
        # Generate final summary
        summary = benchmark.generate_summary_report()
        
        print("\n" + "="*80)
        print("BENCHMARK COMPLETE")
        print("="*80)
        print(f"Total repositories processed: {len(repos)}")
        print(f"Total benchmarks run: {summary.get('total_benchmarks', 0)}")
        print(f"Results saved to: {benchmark.output_dir}")
        print("="*80 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
