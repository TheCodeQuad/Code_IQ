"""
Comprehensive Docstring Truthfulness Evaluator

Evaluates whether code components mentioned in generated docstrings actually exist 
in the repository and whether they are contextually correct.

Core Evaluation Questions:
- When a docstring mentions functions/classes, are those actually real?
- Are they valid in the context of the repository?
- Are cross-file dependencies correctly identified?

Features:
- LLM-based semantic component extraction with regex fallback
- Per-repository dependency graph caching
- Component existence validation
- Cross-file reference detection
- Hallucination detection
- Comprehensive statistics and reporting
- Production-quality code with type hints and error handling

Metrics:
- existence_ratio = existing_components / total_components_mentioned
  (Measures hallucination - higher is better)
- cross_file_ratio = cross_file_mentions / existing_components  
  (Measures context awareness)
- avg_mentions_per_doc = total_mentions / docstrings_analyzed
  (Measures richness of docstrings)

Usage:
    from backend.evaluator.truthfulness_comprehensive import ComprehensiveTruthfulnessEvaluator
    
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir="data/intermediate/navigator_output",
        use_llm=True,
        llm_mode="llama_cpp"
    )
    
    results = evaluator.evaluate_docstring(
        component_id="module.ClassName.method",
        docstring="This method uses function_x() internally...",
        file_path="src/module.py",
        repository_name="my_repo",
        language="python"
    )
    
    summary = evaluator.generate_summary_report(all_results)
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from enum import Enum

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False


class ComponentType(str, Enum):
    """Enumeration of code component types"""
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    PROPERTY = "property"
    MODULE = "module"
    INTERFACE = "interface"
    ENUM = "enum"
    DECORATOR = "decorator"
    VARIABLE = "variable"
    UNKNOWN = "unknown"


@dataclass
class ComponentMention:
    """Represents a component mentioned in a docstring"""
    name: str
    exists: bool
    is_cross_file: bool
    component_type: Optional[str] = None
    file_path: Optional[str] = None
    repository: Optional[str] = None


@dataclass
class DocstringEvaluationResult:
    """Results for a single docstring evaluation"""
    component_id: str
    repository: str
    file_path: str
    language: str
    mentioned_components: List[ComponentMention] = field(default_factory=list)
    total_mentions: int = 0
    existing_mentions: int = 0
    cross_file_mentions: int = 0
    hallucination_rate: float = 0.0
    existence_ratio: float = 0.0


@dataclass
class SystemEvaluationStats:
    """Aggregate statistics for a system across all docstrings"""
    system_name: str
    total_docstrings_analyzed: int = 0
    total_components_mentioned: int = 0
    existing_components: int = 0
    cross_file_mentions: int = 0
    avg_existence_ratio: float = 0.0
    avg_hallucination_rate: float = 0.0
    avg_mentions_per_doc: float = 0.0
    by_language: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_repository: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    hallucinated_components: List[Tuple[str, str]] = field(default_factory=list)


class ComprehensiveTruthfulnessEvaluator:
    """
    Comprehensive evaluator for docstring truthfulness based on component existence
    and contextual correctness in the codebase.
    """
    
    def __init__(
        self,
        navigator_output_dir: str,
        writer_output_dir: Optional[str] = None,
        use_llm: bool = True,
        llm_mode: str = "llama_cpp",
        cache_graphs: bool = True,
        repository_name: Optional[str] = None
    ):
        """
        Initialize the comprehensive truthfulness evaluator.
        
        Args:
            navigator_output_dir: Directory containing navigator output (component graphs)
            writer_output_dir: Directory containing writer agent output (optional, for loading specific repo files)
            use_llm: Whether to use LLM for component extraction (fallback to regex)
            llm_mode: Local LLM mode (llama_cpp)
            cache_graphs: Whether to cache dependency graphs per repository
            repository_name: If provided, only process files for this repository
        """
        self.navigator_output_dir = Path(navigator_output_dir)
        self.writer_output_dir = Path(writer_output_dir) if writer_output_dir else None
        self.repository_name = repository_name
        self.use_llm = use_llm
        self.llm_mode = llm_mode
        self.cache_graphs = cache_graphs
        
        # Initialize LLM if available
        self.llm = None
        if self.use_llm:
            self._initialize_llm()
        
        # Dependency graph cache: repo_name -> component_db
        self.graph_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        logger.info(f"Initialized ComprehensiveTruthfulnessEvaluator with LLM mode: {llm_mode}")
        if repository_name:
            logger.info(f"Repository filter enabled: {repository_name}")
    
    # ==================== LLM INITIALIZATION ====================
    
    def _initialize_llm(self):
        """Initialize the LLM for component extraction"""
        if not LLAMA_CPP_AVAILABLE:
            logger.warning("llama-cpp-python not installed. Falling back to regex extraction.")
            self.use_llm = False
            return
        model_path = project_root / "models" / "qwen2.5-7b-instruct-q3_k_m.gguf"
        if not model_path.exists():
            logger.warning(f"Model not found at {model_path}. Falling back to regex extraction.")
            self.use_llm = False
            return

        try:
            self.llm = Llama(
                model_path=str(model_path),
                n_ctx=8192,
                n_gpu_layers=-1,
                verbose=False
            )
            logger.info(f"Initialized local llama.cpp with model: {model_path.name}")
        except Exception as e:
            logger.warning(f"Failed to initialize llama.cpp: {e}. Falling back to regex.")
            self.use_llm = False
    
    # ==================== DEPENDENCY GRAPH LOADING ====================
    
    def load_dependency_graph(self, repository_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Load dependency graph for a repository from navigator output.
        Uses caching to avoid repeated loading.
        
        Args:
            repository_name: Name of the repository
            
        Returns:
            Dictionary mapping component_id to component data
        """
        # Return cached graph if available
        if self.cache_graphs and repository_name in self.graph_cache:
            return self.graph_cache[repository_name]
        
        component_db = self._load_component_database(repository_name)
        
        # Cache the graph
        if self.cache_graphs:
            self.graph_cache[repository_name] = component_db
        
        return component_db
    
    def load_writer_output(self, repository_name: str) -> List[Dict[str, Any]]:
        """
        Load writer output files filtered by repository name.
        
        Handles both:
        1. Consolidated files: {repository_name}_writer_output.json
        2. Individual component files: aggregated by repository
        
        Args:
            repository_name: Name of the repository (e.g., "testrepo", "test_repo")
            
        Returns:
            List of component dictionaries from writer output
        """
        if not self.writer_output_dir or not self.writer_output_dir.exists():
            logger.warning(f"Writer output directory not found: {self.writer_output_dir}")
            return []
        
        components = []
        
        # First, try to load consolidated files
        search_patterns = [
            f"{repository_name}_writer_output.json",
            f"*{repository_name}*_writer_output.json",
            f"*{repository_name.replace('_', '-')}*_writer_output.json",
            f"*{repository_name.replace('-', '_')}*_writer_output.json",
        ]
        
        found_files = []
        for pattern in search_patterns:
            matching_files = list(self.writer_output_dir.glob(pattern))
            if matching_files:
                found_files.extend(matching_files)
        
        # If we found consolidated files, load them
        if found_files:
            logger.info(f"Found {len(found_files)} consolidated writer output files for repository '{repository_name}'")
            
            for writer_file in found_files:
                try:
                    with open(writer_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Handle different formats
                    if isinstance(data, dict):
                        components.append(data)
                    elif isinstance(data, list):
                        components.extend(data)
                
                except Exception as e:
                    logger.error(f"Error loading {writer_file}: {e}")
            
            return components
        
        # If no consolidated files, load individual component files and filter by repository
        logger.info(f"No consolidated files found. Loading individual component files for repository '{repository_name}'...")
        
        # First, load the dependency graph to know which components belong to this repo
        repo_graph = self.load_dependency_graph(repository_name)
        repo_component_ids = set(repo_graph.keys())
        
        if not repo_component_ids:
            logger.warning(f"No components found in dependency graph for repository '{repository_name}'")
            # List available repositories
            nav_files = list(self.navigator_output_dir.glob("ir_*.json"))
            available_repos = set()
            for nav_file in nav_files:
                # Extract repo name from filename like "ir_testrepo.json"
                repo = nav_file.stem.replace('ir_', '')
                available_repos.add(repo)
                return self._extract_with_llama(docstring, language)
            return []
        
        logger.info(f"Found {len(repo_component_ids)} components in dependency graph for '{repository_name}'")
                # Handle different navigator output formats
                if isinstance(data, dict):
                    # Direct component dictionary (IR format)
                    for key, value in data.items():
                        if isinstance(value, dict):
                            # Store by multiple keys for flexible lookups
                            component_db[key] = value
                            
                            # Also store by component name if structure has it
                            if "name" in value:
                                component_db[value["name"]] = value
                
                elif isinstance(data, list):
                    # List of components
                    for comp_data in data:
                        if isinstance(comp_data, dict):
                            comp_id = comp_data.get("id", comp_data.get("component_id"))
                            if comp_id:
                                component_db[comp_id] = comp_data
                                if "name" in comp_data:
                                    component_db[comp_data["name"]] = comp_data
            
            except Exception as e:
                logger.warning(f"Error loading {nav_file}: {e}")
        
        logger.info(f"Loaded {len(component_db)} components for repository '{repository_name}'")
        return component_db
    
    # ==================== COMPONENT EXTRACTION ====================
    
    def extract_components_from_docstring(
        self,
        docstring: str,
        language: str
    ) -> List[str]:
        """
        Extract code components mentioned in a docstring.
        
        Args:
            docstring: The docstring text to analyze
            language: Programming language (python, javascript, java, etc.)
            
        Returns:
            List of component names mentioned in the docstring
        """
        if self.use_llm and self.llm:
            return self._extract_with_llama(docstring, language)
        
        # Fallback to regex-based extraction
        return self._extract_with_regex(docstring, language)
    
    def _extract_with_llama(self, docstring: str, language: str) -> List[str]:
        """Extract components using llama.cpp"""
        prompt = f"""Extract all custom code components (classes, methods, functions) mentioned in this {language} docstring.
Ignore standard library components. Return only a JSON array of strings with component names.

Docstring: {docstring}

Response (JSON array only, e.g., ["ComponentA", "method_b"]):"""
        
        try:
            response = self.llm(
                prompt,
                max_tokens=512,
                temperature=0.1,
                stop=["</s>", "\n\n"]
            )
            
            response_text = response["choices"][0]["text"].strip()
            
            # Try to parse as JSON array
            match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if match:
                try:
                    components = json.loads(match.group(0))
                    if isinstance(components, list):
                        return [str(c) for c in components]
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Error calling llama.cpp: {e}")
        
        # Fallback to regex
        return self._extract_with_regex(docstring, language)
    
    def _extract_with_regex(self, docstring: str, language: str) -> List[str]:
        """
        Fallback: Extract components using regex patterns.
        Only extracts EXPLICIT code references (backticks, function calls, etc.).
        """
        components = []
        
        # 1. Extract code in backticks: `ComponentName` or `function_name`
        backtick_pattern = r'`([a-zA-Z_][a-zA-Z0-9_]*)`'
        backtick_matches = re.findall(backtick_pattern, docstring)
        components.extend(backtick_matches)
        
        # 2. Extract function/method calls: ComponentName() or function_name()
        func_call_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)'
        func_matches = re.findall(func_call_pattern, docstring)
        components.extend(func_matches)
        
        # 3. Language-specific patterns
        if language == "python":
            # self.method_name, obj.method_name, or ClassName.method_name
            method_pattern = r'\.([a-z_][a-z0-9_]*)\b'
            method_matches = re.findall(method_pattern, docstring)
            components.extend(method_matches)
            
            # Extract CamelCase class names
            camel_case_pattern = r'\b([A-Z][a-zA-Z0-9]*)\b'
            camel_matches = re.findall(camel_case_pattern, docstring)
            components.extend(camel_matches)
        
        elif language in ["javascript", "typescript"]:
            # this.methodName or object.methodName
            method_pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]*)\b'
            method_matches = re.findall(method_pattern, docstring)
            components.extend(method_matches)
            
            # CamelCase class names
            camel_case_pattern = r'\b([A-Z][a-zA-Z0-9]*)\b'
            camel_matches = re.findall(camel_case_pattern, docstring)
            components.extend(camel_matches)
        
        elif language == "java":
            # ClassName.methodName or object.methodName
            method_pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]*)\b'
            method_matches = re.findall(method_pattern, docstring)
            components.extend(method_matches)
            
            # CamelCase class names
            camel_case_pattern = r'\b([A-Z][a-zA-Z0-9]*)\b'
            camel_matches = re.findall(camel_case_pattern, docstring)
            components.extend(camel_matches)
        
        # 4. Filter out common/standard library names
        common_words = {
            'error', 'string', 'number', 'boolean', 'array', 'object',
            'true', 'false', 'null', 'undefined', 'void', 'return',
            'value', 'result', 'data', 'input', 'output', 'type',
            'the', 'and', 'for', 'with', 'this', 'that', 'from', 'into',
            'operation', 'function', 'method', 'class', 'module',
            'list', 'dict', 'set', 'tuple', 'str', 'int', 'float',
            'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
            'console', 'log', 'warn', 'error', 'push', 'pop', 'shift',
            'slice', 'splice', 'join', 'split', 'trim', 'tolowercase',
            'system', 'out', 'println', 'tostring', 'equals', 'hashcode',
            'public', 'private', 'protected', 'static', 'final', 'abstract',
            'interface', 'extends', 'implements', 'super', 'new', 'instanceof'
        }
        
        # Remove duplicates and filter
        components = list(set([
            c for c in components 
            if c.lower() not in common_words 
            and len(c) > 2  # At least 3 characters
            and not c.isdigit()
        ]))
        
        return components
    
    # ==================== COMPONENT VALIDATION ====================
    
    def check_component_existence(
        self,
        component_name: str,
        docstring_file_path: str,
        component_db: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, bool, Optional[str], Optional[str]]:
        """
        Check if a component exists in the dependency graph.
        
        Args:
            component_name: Name of the component to check
            docstring_file_path: File path where the docstring is located
            component_db: Component database for the repository
            
        Returns:
            Tuple of (exists, is_cross_file, component_type, found_file_path)
        """
        exists = False
        is_cross_file = False
        component_type = None
        found_file_path = None
        
        # Normalize the docstring file path
        docstring_file_normalized = str(Path(docstring_file_path)).replace('\\', '/').lower()
        
        # Search in component database with multiple strategies
        # Strategy 1: Exact match by component ID or name
        if component_name in component_db:
            comp_data = component_db[component_name]
            exists = True
            component_type = comp_data.get("type", comp_data.get("component_type"))
            
            # Get the file path
            comp_location = comp_data.get("location", {})
            if isinstance(comp_location, dict):
                found_file_path = comp_location.get("file_path", "")
            else:
                found_file_path = comp_data.get("file_path", "")
            
            if found_file_path:
                found_file_normalized = str(Path(found_file_path)).replace('\\', '/').lower()
                if docstring_file_normalized != found_file_normalized:
                    is_cross_file = True
            
            return exists, is_cross_file, component_type, found_file_path
        
        # Strategy 2: Case-insensitive match
        for comp_id, comp_data in component_db.items():
            comp_name = comp_data.get("name", comp_id.split(".")[-1])
            
            if component_name.lower() == comp_name.lower() or component_name in comp_id:
                exists = True
                component_type = comp_data.get("type", comp_data.get("component_type"))
                
                comp_location = comp_data.get("location", {})
                if isinstance(comp_location, dict):
                    found_file_path = comp_location.get("file_path", "")
                else:
                    found_file_path = comp_data.get("file_path", "")
                
                if found_file_path:
                    found_file_normalized = str(Path(found_file_path)).replace('\\', '/').lower()
                    if docstring_file_normalized != found_file_normalized:
                        is_cross_file = True
                
                break
        
        return exists, is_cross_file, component_type, found_file_path
    
    # ==================== EVALUATION ====================
    
    def evaluate_docstring(
        self,
        component_id: str,
        docstring: str,
        file_path: str,
        repository_name: str,
        language: str
    ) -> DocstringEvaluationResult:
        """
        Evaluate a single docstring for truthfulness.
        
        Args:
            component_id: ID of the component being documented
            docstring: The generated docstring
            file_path: File path of the component
            repository_name: Name of the repository
            language: Programming language
            
        Returns:
            DocstringEvaluationResult object
        """
        # Load component database for this repository
        component_db = self.load_dependency_graph(repository_name)
        
        # Extract mentioned components
        mentioned_names = self.extract_components_from_docstring(docstring, language)
        
        # Check existence of each component
        component_mentions = []
        for comp_name in mentioned_names:
            exists, is_cross_file, comp_type, found_path = self.check_component_existence(
                comp_name, file_path, component_db
            )
            
            component_mentions.append(ComponentMention(
                name=comp_name,
                exists=exists,
                is_cross_file=is_cross_file,
                component_type=comp_type,
                file_path=found_path,
                repository=repository_name
            ))
        
        # Calculate metrics
        total_mentions = len(component_mentions)
        existing_mentions = sum(1 for cm in component_mentions if cm.exists)
        cross_file_mentions = sum(1 for cm in component_mentions if cm.is_cross_file)
        
        # Calculate ratios
        existence_ratio = existing_mentions / total_mentions if total_mentions > 0 else 0.0
        hallucination_rate = (total_mentions - existing_mentions) / total_mentions if total_mentions > 0 else 0.0
        
        return DocstringEvaluationResult(
            component_id=component_id,
            repository=repository_name,
            file_path=file_path,
            language=language,
            mentioned_components=component_mentions,
            total_mentions=total_mentions,
            existing_mentions=existing_mentions,
            cross_file_mentions=cross_file_mentions,
            hallucination_rate=hallucination_rate,
            existence_ratio=existence_ratio
        )
    
    def evaluate_batch(
        self,
        components: List[Dict[str, Any]]
    ) -> List[DocstringEvaluationResult]:
        """
        Evaluate multiple docstrings (batch evaluation).
        
        Args:
            components: List of dictionaries with component data including:
                - component_id: str
                - docstring: str  
                - file_path: str
                - repository: str
                - language: str
                
        Returns:
            List of DocstringEvaluationResult objects
        """
        results = []
        
        for comp_data in tqdm(components, desc="Evaluating docstrings"):
            try:
                result = self.evaluate_docstring(
                    component_id=comp_data.get('component_id', comp_data.get('id', 'unknown')),
                    docstring=comp_data.get('docstring', comp_data.get('generated_docstring', '')),
                    file_path=comp_data.get('file_path', ''),
                    repository_name=comp_data.get('repository', comp_data.get('repo', 'unknown')),
                    language=comp_data.get('language', 'python')
                )
                
                results.append(result)
            
            except Exception as e:
                logger.error(f"Error evaluating component {comp_data.get('component_id', 'unknown')}: {e}")
        
        return results
    
    def evaluate_repository_writer_output(self, repository_name: str) -> List[DocstringEvaluationResult]:
        """
        Evaluate all docstrings from writer output for a specific repository.
        
        This is a convenience method that:
        1. Loads writer output files for the given repository
        2. Evaluates all components in those files
        3. Returns aggregated results
        
        Args:
            repository_name: Name of the repository to evaluate
            
        Returns:
            List of DocstringEvaluationResult objects
        """
        if not self.writer_output_dir:
            raise ValueError("writer_output_dir must be set to use this method")
        
        # Load writer output for this repository
        components = self.load_writer_output(repository_name)
        
        if not components:
            logger.warning(f"No components found in writer output for repository '{repository_name}'")
            return []
        
        # Ensure all components have the repository name set
        for comp in components:
            if 'repository' not in comp and 'repo' not in comp:
                comp['repository'] = repository_name
        
        # Evaluate all components
        results = self.evaluate_batch(components)
        
        return results
    
    # ==================== REPORTING ====================
    
    def generate_summary_report(
        self,
        results: List[DocstringEvaluationResult] | Dict[str, DocstringEvaluationResult]
    ) -> SystemEvaluationStats:
        """
        Generate summary statistics from evaluation results.
        
        Args:
            results: List or dict of DocstringEvaluationResult objects
            
        Returns:
            SystemEvaluationStats object
        """
        # Convert to list if dict
        if isinstance(results, dict):
            results_list = list(results.values())
        else:
            results_list = results
        
        if not results_list:
            return SystemEvaluationStats(system_name="unknown")
        
        # Calculate overall statistics
        total_docstrings = len(results_list)
        total_mentions = sum(r.total_mentions for r in results_list)
        existing_mentions = sum(r.existing_mentions for r in results_list)
        cross_file_mentions = sum(r.cross_file_mentions for r in results_list)
        
        avg_existence_ratio = sum(r.existence_ratio for r in results_list) / total_docstrings if total_docstrings > 0 else 0.0
        avg_hallucination_rate = sum(r.hallucination_rate for r in results_list) / total_docstrings if total_docstrings > 0 else 0.0
        avg_mentions_per_doc = total_mentions / total_docstrings if total_docstrings > 0 else 0.0
        
        # Group by language
        by_language = defaultdict(lambda: {
            'docstrings': 0,
            'mentions': 0,
            'existing': 0,
            'cross_file': 0,
            'existence_ratios': []
        })
        
        for result in results_list:
            lang = result.language
            by_language[lang]['docstrings'] += 1
            by_language[lang]['mentions'] += result.total_mentions
            by_language[lang]['existing'] += result.existing_mentions
            by_language[lang]['cross_file'] += result.cross_file_mentions
            by_language[lang]['existence_ratios'].append(result.existence_ratio)
        
        # Calculate language statistics
        by_language_stats = {}
        for lang, stats in by_language.items():
            avg_existence = sum(stats['existence_ratios']) / len(stats['existence_ratios'])
            by_language_stats[lang] = {
                'docstrings': stats['docstrings'],
                'mentions': stats['mentions'],
                'existing': stats['existing'],
                'cross_file': stats['cross_file'],
                'avg_existence_ratio': avg_existence
            }
        
        # Group by repository
        by_repository = defaultdict(lambda: {
            'docstrings': 0,
            'mentions': 0,
            'existing': 0,
            'cross_file': 0,
            'existence_ratios': []
        })
        
        for result in results_list:
            repo = result.repository
            by_repository[repo]['docstrings'] += 1
            by_repository[repo]['mentions'] += result.total_mentions
            by_repository[repo]['existing'] += result.existing_mentions
            by_repository[repo]['cross_file'] += result.cross_file_mentions
            by_repository[repo]['existence_ratios'].append(result.existence_ratio)
        
        # Calculate repository statistics
        by_repository_stats = {}
        for repo, stats in by_repository.items():
            avg_existence = sum(stats['existence_ratios']) / len(stats['existence_ratios'])
            by_repository_stats[repo] = {
                'docstrings': stats['docstrings'],
                'mentions': stats['mentions'],
                'existing': stats['existing'],
                'cross_file': stats['cross_file'],
                'avg_existence_ratio': avg_existence
            }
        
        # Collect hallucinated components
        hallucinated = []
        for result in results_list:
            for cm in result.mentioned_components:
                if not cm.exists:
                    hallucinated.append((result.component_id, cm.name))
        
        return SystemEvaluationStats(
            system_name="evaluation_summary",
            total_docstrings_analyzed=total_docstrings,
            total_components_mentioned=total_mentions,
            existing_components=existing_mentions,
            cross_file_mentions=cross_file_mentions,
            avg_existence_ratio=avg_existence_ratio,
            avg_hallucination_rate=avg_hallucination_rate,
            avg_mentions_per_doc=avg_mentions_per_doc,
            by_language=by_language_stats,
            by_repository=by_repository_stats,
            hallucinated_components=hallucinated
        )
    
    def save_results_json(
        self,
        results: List[DocstringEvaluationResult] | Dict[str, DocstringEvaluationResult],
        output_file: Path
    ):
        """
        Save evaluation results as JSON.
        
        Args:
            results: List or dict of evaluation results
            output_file: Path to save JSON file
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert results to dict format
        if isinstance(results, list):
            results_dict = {str(i): r for i, r in enumerate(results)}
        else:
            results_dict = results
        
        # Serialize to JSON-compatible format
        serializable_results = {}
        for key, result in results_dict.items():
            serializable_results[key] = {
                "component_id": result.component_id,
                "repository": result.repository,
                "file_path": result.file_path,
                "language": result.language,
                "total_mentions": result.total_mentions,
                "existing_mentions": result.existing_mentions,
                "cross_file_mentions": result.cross_file_mentions,
                "hallucination_rate": result.hallucination_rate,
                "existence_ratio": result.existence_ratio,
                "mentioned_components": [
                    {
                        "name": cm.name,
                        "exists": cm.exists,
                        "is_cross_file": cm.is_cross_file,
                        "component_type": cm.component_type,
                        "file_path": cm.file_path,
                        "repository": cm.repository
                    }
                    for cm in result.mentioned_components
                ]
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, indent=2)
        
        logger.info(f"Saved results to {output_file}")
    
    def generate_markdown_report(
        self,
        results: List[DocstringEvaluationResult] | Dict[str, DocstringEvaluationResult],
        output_file: Path
    ):
        """
        Generate a comprehensive markdown report.
        
        Args:
            results: List or dict of evaluation results
            output_file: Path to save markdown report
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to list if needed
        if isinstance(results, dict):
            results_list = list(results.values())
        else:
            results_list = results
        
        # Generate summary
        summary = self.generate_summary_report(results_list)
        
        # Build markdown report
        report = "# Docstring Truthfulness Evaluation Report\n\n"
        
        # Executive Summary
        report += "## Executive Summary\n\n"
        report += f"- **Total Docstrings Analyzed:** {summary.total_docstrings_analyzed}\n"
        report += f"- **Total Components Mentioned:** {summary.total_components_mentioned}\n"
        report += f"- **Existing Components:** {summary.existing_components}\n"
        report += f"- **Cross-file References:** {summary.cross_file_mentions}\n"
        report += f"- **Average Existence Ratio:** {summary.avg_existence_ratio:.2%}\n"
        report += f"- **Average Hallucination Rate:** {summary.avg_hallucination_rate:.2%}\n"
        report += f"- **Average Mentions Per Docstring:** {summary.avg_mentions_per_doc:.2f}\n\n"
        
        # Metrics Definition
        report += "### Metrics Definition\n\n"
        report += "- **Existence Ratio:** Percentage of mentioned components that exist in the codebase (higher is better)\n"
        report += "- **Hallucination Rate:** Percentage of mentioned components that don't exist (lower is better)\n"
        report += "- **Cross-file References:** Components from different files (indicates context awareness)\n"
        report += "- **Mentions Per Doc:** Average number of components referenced per docstring (richness)\n\n"
        
        # Language Breakdown
        report += "## Language Breakdown\n\n"
        report += "| Language | Docstrings | Mentions | Existing | Existence Ratio | Hallucination Rate |\n"
        report += "|----------|-----------|----------|----------|-----------------|--------------------|\n"
        
        for language, stats in sorted(summary.by_language.items()):
            report += f"| {language} | {stats['docstrings']} | {stats['mentions']} | {stats['existing']} | "
            report += f"{stats['avg_existence_ratio']:.2%} | {1 - stats['avg_existence_ratio']:.2%} |\n"
        
        # Repository Breakdown
        if summary.by_repository:
            report += "\n## Repository Breakdown\n\n"
            report += "| Repository | Docstrings | Mentions | Existing | Existence Ratio |\n"
            report += "|-----------|-----------|----------|----------|----------------|\n"
            
            for repository, stats in sorted(summary.by_repository.items()):
                report += f"| {repository} | {stats['docstrings']} | {stats['mentions']} | "
                report += f"{stats['existing']} | {stats['avg_existence_ratio']:.2%} |\n"
        
        # Top Performers
        report += "\n## Top Performers (Highest Existence Ratio)\n\n"
        sorted_results = sorted(results_list, key=lambda x: x.existence_ratio, reverse=True)[:10]
        
        if sorted_results:
            report += "| Component | Language | Mentions | Existing | Existence Ratio |\n"
            report += "|-----------|----------|----------|----------|----------------|\n"
            
            for result in sorted_results:
                report += f"| {result.component_id} | {result.language} | {result.total_mentions} | "
                report += f"{result.existing_mentions} | {result.existence_ratio:.2%} |\n"
        
        # Hallucination Cases
        report += "\n## Hallucination Analysis\n\n"
        if summary.hallucinated_components:
            report += f"Found **{len(summary.hallucinated_components)}** hallucinated component references.\n\n"
            report += "| Component | Hallucinated Reference |\n"
            report += "|-----------|----------------------|\n"
            
            for comp_id, comp_name in summary.hallucinated_components[:25]:
                report += f"| {comp_id} | `{comp_name}` |\n"
            
            if len(summary.hallucinated_components) > 25:
                report += f"\n*... and {len(summary.hallucinated_components) - 25} more*\n"
        else:
            report += "✅ **No hallucinations detected!**\n"
        
        # Cross-file References
        report += "\n## Cross-file Reference Analysis\n\n"
        cross_file_refs = []
        for result in results_list:
            for cm in result.mentioned_components:
                if cm.is_cross_file:
                    cross_file_refs.append((result.component_id, cm.name, cm.file_path))
        
        if cross_file_refs:
            report += f"Identified **{len(cross_file_refs)}** cross-file references, indicating good contextual awareness.\n\n"
            report += "| Component | Reference | Source File |\n"
            report += "|-----------|-----------|-------------|\n"
            
            for comp_id, ref_name, file_path in cross_file_refs[:20]:
                file_display = Path(file_path).name if file_path else "Unknown"
                report += f"| {comp_id} | `{ref_name}` | {file_display} |\n"
            
            if len(cross_file_refs) > 20:
                report += f"\n*... and {len(cross_file_refs) - 20} more*\n"
        else:
            report += "No cross-file references found.\n"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Saved markdown report to {output_file}")


# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Comprehensive Docstring Truthfulness Evaluation"
    )
    parser.add_argument(
        "--input", 
        type=str, 
        required=True,
        help="Input JSON file with docstrings (from agent output or completeness evaluation)"
    )
    parser.add_argument(
        "--navigator-dir",
        type=str,
        default="data/intermediate/navigator_output",
        help="Directory containing navigator output files"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/validation/truthfulness",
        help="Directory to save evaluation results"
    )
    parser.add_argument(
        "--llm-mode",
        type=str,
        default="llama_cpp",
        help="Local LLM mode for component extraction (llama_cpp only)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM and use regex-only extraction"
    )
    
    args = parser.parse_args()
    
    # Initialize evaluator
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir=args.navigator_dir,
        use_llm=not args.no_llm,
        llm_mode=args.llm_mode
    )
    
    logger.info(f"Loading input from {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
    
    # Handle different input formats
    if isinstance(input_data, dict) and not isinstance(next(iter(input_data.values()), None), dict):
        # Likely a systems dict
        components = []
        for system_data in input_data.values():
            if isinstance(system_data, list):
                components.extend(system_data)
    elif isinstance(input_data, list):
        components = input_data
    else:
        components = [input_data]
    
    # Evaluate
    logger.info(f"Evaluating {len(components)} components")
    results = evaluator.evaluate_batch(components)
    
    # Save results
    output_path = Path(args.output_dir)
    json_file = output_path / "truthfulness_results.json"
    md_file = output_path / "truthfulness_report.md"
    
    evaluator.save_results_json(results, json_file)
    evaluator.generate_markdown_report(results, md_file)
    
    logger.info("Evaluation complete!")
