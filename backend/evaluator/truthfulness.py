"""
Docstring Truthfulness Evaluator for Code_IQ

Evaluates whether components mentioned in generated docstrings actually exist in the codebase.
Checks for:
1. Component existence (are mentioned components real?)
2. Cross-file references (are dependencies correctly identified?)
3. Hallucination detection (are non-existent components mentioned?)

Usage:
    python -m backend.evaluator.truthfulness --writer-dir data/intermediate/agent_output/writer
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from tqdm import tqdm
from collections import defaultdict
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.utils.logger import get_logger
from backend.models.code_component import CodeComponent, ComponentType
from backend.utils.paths import DATA_ROOT

logger = get_logger(__name__)

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    logger.warning("llama-cpp-python not installed. Falling back to regex-based extraction.")


@dataclass
class ComponentMention:
    """Represents a component mentioned in a docstring"""
    name: str
    exists: bool
    is_cross_file: bool
    component_type: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class TruthfulnessResult:
    """Results for a single docstring evaluation"""
    component_id: str
    file_path: str
    language: str
    mentioned_components: List[ComponentMention]
    total_mentions: int
    existing_mentions: int
    cross_file_mentions: int
    hallucination_rate: float
    existence_ratio: float


class TruthfulnessEvaluator:
    """
    Evaluates the truthfulness of generated docstrings by checking if mentioned
    components actually exist in the codebase.
    """
    
    def __init__(
        self,
        writer_output_dir: str,
        navigator_output_dir: str,
        use_llm: bool = True,
        llm_mode: str = "llama_cpp",  # local llama.cpp only
        repository_name: Optional[str] = None
    ):
        """
        Initialize the truthfulness evaluator.
    Do NOT return generic docstring words, verbs, or section words such as Adds, Sum,
    Throws, Returns, Parameters, Args, Result, Error, Value, Data, Input, Output.

        
        Args:
            writer_output_dir: Directory containing writer agent output JSON files
            navigator_output_dir: Directory containing navigator output (DAGs, components)
            use_llm: Whether to use LLM for component extraction (fallback to regex)
            llm_mode: Local LLM mode (llama_cpp only)
        """
        self.writer_output_dir = Path(writer_output_dir)
        self.navigator_output_dir = Path(navigator_output_dir)
        self.use_llm = use_llm
        self.llm_mode = llm_mode
        self.repository_name = repository_name

        # Opt-in debug logging. Keep default quiet for UI runs.
        # Enable with: set TRUTHFULNESS_DEBUG=1 (cmd) or $env:TRUTHFULNESS_DEBUG="1" (PowerShell)
        self.debug = str(os.getenv("TRUTHFULNESS_DEBUG", "0")).strip().lower() in {"1", "true", "yes", "y"}
        
        # Initialize LLM if available
        self.llm = None
        if self.use_llm:
            self._initialize_llm()
        
        # Repo-scoped dependency graph cache: repo_name -> component_db
        self.graph_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Backward-compatible default component database (filled on demand)
        self.component_db: Dict[str, Dict[str, Any]] = {}

        if self.debug:
            logger.info(
                "[truthfulness-debug] writer_output_dir=%s navigator_output_dir=%s use_llm=%s llm_mode=%s",
                str(self.writer_output_dir),
                str(self.navigator_output_dir),
                self.use_llm,
                self.llm_mode,
            )
            if self.repository_name:
                logger.info("[truthfulness-debug] repository filter=%s", self.repository_name)
    
    def _initialize_llm(self):
        """Initialize the LLM for component extraction"""
        if not LLAMA_CPP_AVAILABLE:
            logger.warning("llama-cpp-python not installed. Falling back to regex-based extraction.")
            self.use_llm = False
            return

        # Always use the local Qwen model for truthfulness extraction.
        model_path = project_root / "models" / "qwen2.5-coder-14b-instruct-q4_k_m.gguf"

        if not model_path.exists():
            logger.warning(f"Model not found at {model_path}. Falling back to regex extraction.")
            self.use_llm = False
            return

        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=8192,
            n_gpu_layers=-1,  # Use GPU if available
            verbose=False
        )
        logger.info(f"Initialized local llama.cpp with model: {model_path.name}")
    
    def _load_component_database(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all components from navigator output files.
        
        Returns:
            Dictionary mapping component_id to component data
        """
        component_db = {}
        
        # Look for navigator output files
        nav_files = list(self.navigator_output_dir.glob("**/*.json"))
        
        for nav_file in nav_files:
            try:
                with open(nav_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle different navigator output formats
                if isinstance(data, dict):
                    # Check if it's a DAG export
                    if "nodes" in data:
                        for node in data["nodes"]:
                            comp_id = node.get("id", node.get("component_id"))
                            if comp_id:
                                component_db[comp_id] = node
                    
                    # Check if it's a component map
                    elif "components" in data:
                        for comp_id, comp_data in data["components"].items():
                            component_db[comp_id] = comp_data
                    
                    # Direct component dictionary
                    else:
                        for key, value in data.items():
                            if isinstance(value, dict) and ("type" in value or "component_type" in value):
                                component_db[key] = value
                
                elif isinstance(data, list):
                    # List of components
                    for comp_data in data:
                        if isinstance(comp_data, dict):
                            comp_id = comp_data.get("id", comp_data.get("component_id"))
                            if comp_id:
                                component_db[comp_id] = comp_data
            
            except Exception as e:
                logger.warning(f"Error loading {nav_file}: {e}")
        
        return component_db

    def load_dependency_graph(self, repo_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Load a repository-specific dependency graph / component map.

        This prefers the IR file produced by Navigator:
        data/intermediate/navigator_output/ir_{repo_name}.json

        If the file is missing, it falls back to the broader navigator scan.
        """
        if repo_name in self.graph_cache:
            return self.graph_cache[repo_name]

        ir_path = self.navigator_output_dir / f"ir_{repo_name}.json"
        component_db: Dict[str, Dict[str, Any]] = {}

        if ir_path.exists():
            try:
                with open(ir_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if isinstance(data, dict):
                    component_db = data
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            comp_id = item.get("id", item.get("component_id"))
                            if comp_id:
                                component_db[comp_id] = item

                logger.info(f"Loaded {len(component_db)} components from dependency graph for repo '{repo_name}'")
            except Exception as e:
                logger.warning(f"Error loading dependency graph {ir_path}: {e}")
                component_db = {}

        if not component_db:
            # Fall back to the broader scan of navigator outputs
            component_db = self._load_component_database()
            logger.info(f"Loaded {len(component_db)} components from navigator output")

        self.graph_cache[repo_name] = component_db
        return component_db
    
    def extract_components_from_docstring(self, docstring: str, language: str) -> List[str]:
        """
        Extract code components mentioned in a docstring.
        
        Args:
            docstring: The docstring text to analyze
            language: Programming language (python, javascript, java, etc.)
            
        Returns:
            List of component names mentioned in the docstring
        """
        if self.use_llm and self.llm:
            llm_components = self._extract_with_llama(docstring, language)
            if llm_components:
                return llm_components

        # If the model is unavailable or unusable, fall back to a strict
        # backtick-only extractor so we only keep explicit code references.
        return self._extract_backtick_mentions(docstring)

    def _extract_backtick_mentions(self, docstring: str) -> List[str]:
        """Extract explicit names written inside backticks only."""
        backtick_pattern = r'`([a-zA-Z_][a-zA-Z0-9_]*)`'
        return self._dedupe_and_filter_components(re.findall(backtick_pattern, docstring))

    def _extract_explicit_mentions(self, docstring: str, language: str) -> List[str]:
        """Extract explicit code references from the docstring text."""
        components = []

        # Split into lines so we can ignore docstring section headings like Args/Returns.
        lines = docstring.splitlines()
        section_headers = {
            "args", "arguments", "parameters", "returns", "raises", "yields",
            "examples", "example", "attributes", "notes", "seealso", "see also",
            "todo", "warnings", "refs", "reference", "references", "methods",
            "properties", "constructor parameters"
        }

        # 1. Extract code in backticks: `ComponentName` or `function_name`
        backtick_pattern = r'`([a-zA-Z_][a-zA-Z0-9_]*)`'
        components.extend(re.findall(backtick_pattern, docstring))

        # 1b. Extract plain-text code-like identifiers such as InMemoryCache,
        # UserManager, or Person even when they are not wrapped in backticks.
        camel_case_pattern = r'\b([A-Z][A-Za-z0-9]*)\b'
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            lower_stripped = stripped.lower().rstrip(":")
            if lower_stripped in section_headers:
                continue

            # Skip obvious prose headings / sentences that start with common verbs.
            if re.match(r'^(Determines|Represents|Initialize|Returns|Checks|Creates|Calculates|Extracts|Uses|Computes|Gets|Sets|Loads|Saves|Validates|Processes|Converts)\b', stripped):
                # Still allow the line to contribute identifiers later in the line.
                tail = re.sub(r'^(Determines|Represents|Initialize|Returns|Checks|Creates|Calculates|Extracts|Uses|Computes|Gets|Sets|Loads|Saves|Validates|Processes|Converts)\b', '', stripped, count=1).strip()
                components.extend(re.findall(camel_case_pattern, tail))
                continue

            components.extend(re.findall(camel_case_pattern, stripped))

        # 2. Extract function/method calls: ComponentName() or function_name()
        func_call_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)'
        components.extend(re.findall(func_call_pattern, docstring))

        # 3. Language-specific dotted method calls
        if language == "python":
            components.extend(re.findall(r'\.([a-z_][a-z0-9_]*)\b', docstring))
        elif language in ["javascript", "typescript", "java"]:
            components.extend(re.findall(r'\.([a-zA-Z_][a-zA-Z0-9_]*)\b', docstring))

        return self._dedupe_and_filter_components(components)

    def _merge_component_mentions(self, explicit_components: List[str], llm_components: List[str]) -> List[str]:
        """Merge explicit mentions with LLM-extracted mentions, keeping explicit ones."""
        merged = list(explicit_components)
        for component in llm_components:
            if component not in merged:
                merged.append(component)
        return self._dedupe_and_filter_components(merged)

    def _dedupe_and_filter_components(self, components: List[str]) -> List[str]:
        """Remove duplicates and filter out common noise words."""
        common_words = {
            'error', 'string', 'number', 'boolean', 'array', 'object',
            'true', 'false', 'null', 'undefined', 'void', 'return',
            'value', 'result', 'data', 'input', 'output', 'type',
            'adds', 'sum', 'throws',
            'the', 'and', 'for', 'with', 'this', 'that', 'from', 'into',
            'operation', 'function', 'method', 'class', 'module',
            'list', 'dict', 'set', 'tuple', 'str', 'int', 'float',
            'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
            'console', 'log', 'warn', 'error', 'push', 'pop', 'shift',
            'slice', 'splice', 'join', 'split', 'trim', 'tolowercase',
            'system', 'out', 'println', 'tostring', 'equals', 'hashcode',
            'determines', 'represents', 'initialize', 'returns', 'checks',
            'creates', 'calculates', 'extracts', 'uses', 'computes', 'gets',
            'sets', 'loads', 'saves', 'validates', 'processes', 'converts',
            'args', 'arguments', 'parameters', 'raises', 'yields', 'examples',
            'example', 'attributes', 'notes', 'seealso', 'see also', 'todo',
            'warnings', 'refs', 'reference', 'references', 'methods',
            'properties', 'constructor parameters'
        }

        seen = set()
        filtered = []
        for component in components:
            component_str = str(component).strip()
            if not component_str:
                continue
            if component_str.lower() in common_words:
                continue
            if len(component_str) <= 2 or component_str.isdigit():
                continue
            if component_str not in seen:
                seen.add(component_str)
                filtered.append(component_str)
        return filtered

    def _build_extraction_prompt(self, docstring: str, language: str) -> str:
        """Build the local-model prompt for component extraction."""
        return f"""
Please extract all the non-common (very likely to be newly-defined in the repository)
code components (classes, methods, functions) mentioned in the following {language} docstring.

Treat plain-text code-like names as explicit mentions too if they look like identifiers,
for example: InMemoryCache, UserManager, Person, CacheManager.

Ignore the example part of the docstring if it exists (the code component you extract should not come from example code).

For example, "List" is a very common class, so it should not be included.
On the other hand, "InMemoryCache" is not a common class, so it should be included.

Return only a Python list of strings with the exact names.
If no code components are mentioned, return an empty list.

Docstring:
```
{docstring}
```

Format your response as a Python list wrapped in XML tags like this:
<python_list>["ClassA", "method_b", "function_c"]</python_list>
"""
    
    def _extract_with_llama(self, docstring: str, language: str) -> List[str]:
        """Extract components using llama.cpp."""
        prompt = self._build_extraction_prompt(docstring, language)
        
        try:
            response = self.llm(
                prompt,
                max_tokens=512,
                temperature=0.1,
                stop=["</s>", "\n\n"]
            )
            
            response_text = response["choices"][0]["text"].strip()
            parsed_components = self._parse_llm_component_list(response_text)
            if parsed_components:
                return parsed_components
        
        except Exception as e:
            logger.error(f"Error calling llama.cpp: {e}")

        # If the local model fails, return only explicit backtick mentions.
        return self._extract_backtick_mentions(docstring)

    def _parse_llm_component_list(self, response_text: str) -> List[str]:
        """Parse a list of component names from an LLM response."""
        candidate_texts = [response_text]

        python_list_match = re.search(r"<python_list>\s*(.*?)\s*</python_list>", response_text, re.DOTALL | re.IGNORECASE)
        if python_list_match:
            candidate_texts.insert(0, python_list_match.group(1))

        bracket_match = re.search(r"\[.*?\]", response_text, re.DOTALL)
        if bracket_match:
            candidate_texts.insert(0, bracket_match.group(0))

        for candidate in candidate_texts:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    return self._dedupe_and_filter_components([str(item) for item in parsed])
            except Exception:
                pass

            string_items = re.findall(r'"([^\"]+)"|\'([^\']+)\'', candidate)
            flattened = [item[0] or item[1] for item in string_items if (item[0] or item[1]).strip()]
            if flattened:
                return self._dedupe_and_filter_components(flattened)

            bare_items = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", candidate)
            if candidate.strip().startswith("[") and bare_items:
                return self._dedupe_and_filter_components(bare_items)

        return []
    
    def _extract_with_regex(self, docstring: str, language: str) -> List[str]:
        """
        Fallback: Extract components using regex patterns.
        Only extracts EXPLICIT code references (backticks, function calls, etc.).
        Does NOT extract regular English words to avoid false positives.
        """
        return self._extract_explicit_mentions(docstring, language)
    
    def check_component_existence(
        self,
        component_name: str,
        docstring_file_path: str
    ) -> Tuple[bool, bool, Optional[str], Optional[str]]:
        """
        Check if a component exists in the codebase.
        
        Args:
            component_name: Name of the component to check
            docstring_file_path: File path where the docstring is located
            
        Returns:
            Tuple of (exists, is_cross_file, component_type, found_file_path)
        """
        exists = False
        is_cross_file = False
        component_type = None
        found_file_path = None
        
        # Normalize the docstring file path for comparison
        docstring_file_normalized = str(Path(docstring_file_path)).replace('\\', '/')
        
        # Search in component database
        for comp_id, comp_data in self.component_db.items():
            # Check if component name matches
            comp_name = comp_data.get("name", comp_id.split(".")[-1])
            
            if component_name.lower() == comp_name.lower() or component_name in comp_id:
                exists = True
                component_type = comp_data.get("type", comp_data.get("component_type"))
                
                # Get the file path of the found component
                comp_location = comp_data.get("location", {})
                if isinstance(comp_location, dict):
                    found_file_path = comp_location.get("file_path", "")
                else:
                    found_file_path = comp_data.get("file_path", "")
                
                # Normalize found file path
                if found_file_path:
                    found_file_normalized = str(Path(found_file_path)).replace('\\', '/')
                    
                    # Check if it's a cross-file reference
                    if docstring_file_normalized != found_file_normalized:
                        is_cross_file = True
                
                break

        if self.debug:
            logger.info(
                "[truthfulness-debug] mention='%s' exists=%s cross_file=%s type=%s found_path=%s",
                component_name,
                exists,
                is_cross_file,
                component_type,
                found_file_path,
            )
        
        return exists, is_cross_file, component_type, found_file_path
    
    def evaluate_docstring(
        self,
        component_id: str,
        docstring: str,
        file_path: str,
        language: str,
        repo_name: Optional[str] = None
    ) -> TruthfulnessResult:
        """
        Evaluate a single docstring for truthfulness.
        
        Args:
            component_id: ID of the component being documented
            docstring: The generated docstring
            file_path: File path of the component
            language: Programming language
            
        Returns:
            TruthfulnessResult object
        """
        if repo_name:
            self.component_db = self.load_dependency_graph(repo_name)

        # Extract mentioned components
        mentioned_components = self.extract_components_from_docstring(docstring, language)

        if self.debug:
            preview = (docstring[:240] + "…") if len(docstring) > 240 else docstring
            logger.info(
                "[truthfulness-debug] component_id=%s language=%s file_path=%s extracted_mentions=%s docstring_preview=%r",
                component_id,
                language,
                file_path,
                mentioned_components,
                preview,
            )

        # If the docstring doesn't mention any components, it can't hallucinate
        # component references. Treat as fully truthful.
        if not mentioned_components:
            if self.debug:
                logger.info(
                    "[truthfulness-debug] component_id=%s: no explicit component references found; existence_ratio=1.0",
                    component_id,
                )
            return TruthfulnessResult(
                component_id=component_id,
                file_path=file_path,
                language=language,
                mentioned_components=[],
                total_mentions=0,
                existing_mentions=0,
                cross_file_mentions=0,
                hallucination_rate=0.0,
                existence_ratio=1.0,
            )
        
        # Check existence of each component
        component_mentions = []
        for comp_name in mentioned_components:
            exists, is_cross_file, comp_type, found_path = self.check_component_existence(
                comp_name, file_path
            )
            
            component_mentions.append(ComponentMention(
                name=comp_name,
                exists=exists,
                is_cross_file=is_cross_file,
                component_type=comp_type,
                file_path=found_path
            ))
        
        # Calculate metrics
        total_mentions = len(component_mentions)
        existing_mentions = sum(1 for cm in component_mentions if cm.exists)
        cross_file_mentions = sum(1 for cm in component_mentions if cm.is_cross_file)
        
        # Calculate ratios
        existence_ratio = existing_mentions / total_mentions if total_mentions > 0 else 1.0
        hallucination_rate = (total_mentions - existing_mentions) / total_mentions if total_mentions > 0 else 0.0

        if self.debug:
            missing = [cm.name for cm in component_mentions if not cm.exists]
            logger.info(
                "[truthfulness-debug] component_id=%s total_mentions=%d existing=%d missing=%s existence_ratio=%.3f hallucination_rate=%.3f",
                component_id,
                total_mentions,
                existing_mentions,
                missing,
                existence_ratio,
                hallucination_rate,
            )
        
        return TruthfulnessResult(
            component_id=component_id,
            file_path=file_path,
            language=language,
            mentioned_components=component_mentions,
            total_mentions=total_mentions,
            existing_mentions=existing_mentions,
            cross_file_mentions=cross_file_mentions,
            hallucination_rate=hallucination_rate,
            existence_ratio=existence_ratio
        )
    
    def _infer_repo_name(self, writer_file: Path, data: Any) -> str:
        """Infer repository name from a writer output file."""
        def _repo_from_path(path_value: Any) -> str:
            if not path_value:
                return ""

            path_text = str(path_value)
            path = Path(path_text)

            parts_lower = [part.lower() for part in path.parts]
            if "repositories" in parts_lower:
                repo_index = parts_lower.index("repositories")
                if repo_index + 1 < len(path.parts):
                    return path.parts[repo_index + 1]

            match = re.search(r"[\\/](?:repositories|repository)[\\/](?P<repo>[^\\/]+)", path_text, re.IGNORECASE)
            if match:
                return match.group("repo")

            return ""

        stem = writer_file.stem

        if isinstance(data, dict):
            for candidate in (data.get("file_path"), data.get("path")):
                repo = _repo_from_path(candidate)
                if repo:
                    return repo

            location = data.get("location")
            if isinstance(location, dict):
                repo = _repo_from_path(location.get("file_path") or location.get("path"))
                if repo:
                    return repo

        if stem.endswith("_writer_output"):
            return stem[: -len("_writer_output")]
        if isinstance(data, dict):
            repo = data.get("repository") or data.get("repo")
            if repo:
                return str(repo)
        return stem.split("_")[0]

    def evaluate_all(self) -> Dict[str, TruthfulnessResult]:
        """
        Evaluate all docstrings in the writer output directory.
        
        Returns:
            Dictionary mapping component_id to TruthfulnessResult
        """
        results = {}
        
        # Load all writer output files
        writer_files = list(self.writer_output_dir.glob("*.json"))
        evaluated_files = 0
        
        logger.info(f"Scanning {len(writer_files)} writer output files")
        if self.debug:
            logger.info("[truthfulness-debug] writer_files=%s", [wf.name for wf in writer_files])
        
        def _infer_file_path(component_id: str, fallback: str = "") -> str:
            comp_data = self.component_db.get(component_id)
            if isinstance(comp_data, dict):
                loc = comp_data.get("location")
                if isinstance(loc, dict) and loc.get("file_path"):
                    return loc.get("file_path")
                if comp_data.get("file_path"):
                    return comp_data.get("file_path")
            return fallback

        def _infer_language(payload: dict, default: str = "python") -> str:
            lang = payload.get("language")
            if lang:
                return lang
            metadata = payload.get("metadata")
            if isinstance(metadata, dict):
                return metadata.get("component_language") or default
            return default

        for writer_file in tqdm(writer_files, desc="Evaluating docstrings"):
            try:
                with open(writer_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if self.debug:
                    logger.info(
                        "[truthfulness-debug] processing_writer_file=%s top_level_type=%s",
                        writer_file.name,
                        type(data).__name__,
                    )

                repo_name = self._infer_repo_name(writer_file, data)
                if self.repository_name and repo_name != self.repository_name:
                    if self.debug:
                        logger.info(
                            "[truthfulness-debug] skipping_writer_file=%s inferred_repo=%s filter=%s",
                            writer_file.name,
                            repo_name,
                            self.repository_name,
                        )
                    continue

                self.component_db = self.load_dependency_graph(repo_name)

                # Two supported writer formats:
                # (A) Per-component JSON: {"component_id": ..., "docstring": ...}
                # (B) Consolidated map: {"comp_id": {"docstring": ...}, ...}
                if isinstance(data, dict) and ("component_id" in data or "docstring" in data):
                    component_id = data.get("component_id", writer_file.stem)
                    docstring = data.get("docstring", "")
                    language = _infer_language(data)

                    file_path = data.get("file_path", "")
                    if not file_path and "location" in data:
                        location = data["location"]
                        if isinstance(location, dict):
                            file_path = location.get("file_path", "")
                    file_path = _infer_file_path(component_id, file_path)

                    docstring = re.sub(r'</?DOCSTRING>', '', docstring).strip()
                    if docstring:
                        results[component_id] = self.evaluate_docstring(
                            component_id=component_id,
                            docstring=docstring,
                            file_path=file_path,
                            language=language,
                            repo_name=repo_name,
                        )
                        evaluated_files += 1

                elif isinstance(data, dict):
                    # Consolidated writer output
                    if self.debug:
                        logger.info(
                            "[truthfulness-debug] consolidated_writer_output entries=%d file=%s",
                            len(data),
                            writer_file.name,
                        )
                    for component_id, payload in data.items():
                        if not isinstance(payload, dict):
                            continue
                        docstring = payload.get("docstring", "")
                        if not docstring:
                            continue
                        language = _infer_language(payload)
                        file_path = _infer_file_path(component_id, payload.get("file_path", ""))
                        docstring = re.sub(r'</?DOCSTRING>', '', docstring).strip()

                        results[component_id] = self.evaluate_docstring(
                            component_id=component_id,
                            docstring=docstring,
                            file_path=file_path,
                            language=language,
                            repo_name=repo_name,
                        )
                        evaluated_files += 1
            
            except Exception as e:
                logger.error(f"Error processing {writer_file}: {e}")

        if self.debug:
            logger.info(
                "[truthfulness-debug] evaluated_writer_files=%d repository_filter=%s",
                evaluated_files,
                self.repository_name or "<none>",
            )
        
        return results
    
    def generate_report(
        self,
        results: Dict[str, TruthfulnessResult],
        output_dir: Path
    ):
        """
        Generate a comprehensive truthfulness evaluation report.
        
        Args:
            results: Dictionary of evaluation results
            output_dir: Directory to save the report
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save detailed results as JSON
        results_dict = {
            comp_id: {
                "component_id": result.component_id,
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
                        "file_path": cm.file_path
                    }
                    for cm in result.mentioned_components
                ]
            }
            for comp_id, result in results.items()
        }
        
        json_output = output_dir / "truthfulness_evaluation_detailed.json"
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, indent=2)
        
        logger.info(f"Saved detailed results to {json_output}")
        
        # Generate markdown report
        self._generate_markdown_report(results, output_dir)
    
    def _generate_markdown_report(
        self,
        results: Dict[str, TruthfulnessResult],
        output_dir: Path
    ):
        """Generate a markdown summary report"""
        
        # Calculate aggregate statistics
        total_docstrings = len(results)
        total_components_mentioned = sum(r.total_mentions for r in results.values())
        total_existing = sum(r.existing_mentions for r in results.values())
        total_cross_file = sum(r.cross_file_mentions for r in results.values())
        
        avg_existence_ratio = sum(r.existence_ratio for r in results.values()) / total_docstrings if total_docstrings > 0 else 0
        avg_hallucination_rate = sum(r.hallucination_rate for r in results.values()) / total_docstrings if total_docstrings > 0 else 0
        avg_mentions_per_doc = total_components_mentioned / total_docstrings if total_docstrings > 0 else 0
        
        # Group by language
        by_language = defaultdict(list)
        for result in results.values():
            by_language[result.language].append(result)
        
        # Generate markdown
        report = "# Docstring Truthfulness Evaluation Report\n\n"
        report += f"**Generated:** {Path.cwd()}\n\n"
        report += "---\n\n"
        
        # Overall Summary
        report += "## Overall Summary\n\n"
        report += f"- **Total Docstrings Analyzed:** {total_docstrings}\n"
        report += f"- **Total Components Mentioned:** {total_components_mentioned}\n"
        report += f"- **Existing Components:** {total_existing}\n"
        report += f"- **Cross-file References:** {total_cross_file}\n"
        report += f"- **Average Existence Ratio:** {avg_existence_ratio:.2%}\n"
        report += f"- **Average Hallucination Rate:** {avg_hallucination_rate:.2%}\n"
        report += f"- **Average Mentions Per Docstring:** {avg_mentions_per_doc:.2f}\n\n"
        
        # Metrics explanation
        report += "### Metrics Explanation\n\n"
        report += "- **Existence Ratio:** Percentage of mentioned components that actually exist in the codebase (higher is better)\n"
        report += "- **Hallucination Rate:** Percentage of mentioned components that don't exist (lower is better)\n"
        report += "- **Cross-file References:** Number of mentioned components from other files (indicates good context awareness)\n\n"
        
        # Language Breakdown
        report += "## Language Breakdown\n\n"
        report += "| Language | Docstrings | Components Mentioned | Existing | Existence Ratio | Hallucination Rate |\n"
        report += "|----------|-----------|---------------------|----------|-----------------|--------------------|\n"
        
        for language, lang_results in sorted(by_language.items()):
            lang_total = len(lang_results)
            lang_mentions = sum(r.total_mentions for r in lang_results)
            lang_existing = sum(r.existing_mentions for r in lang_results)
            lang_existence = sum(r.existence_ratio for r in lang_results) / lang_total if lang_total > 0 else 0
            lang_hallucination = sum(r.hallucination_rate for r in lang_results) / lang_total if lang_total > 0 else 0
            
            report += f"| {language} | {lang_total} | {lang_mentions} | {lang_existing} | {lang_existence:.2%} | {lang_hallucination:.2%} |\n"
        
        # Top Performers
        report += "\n## Top Performers (Highest Existence Ratio)\n\n"
        sorted_results = sorted(results.items(), key=lambda x: x[1].existence_ratio, reverse=True)[:10]
        
        report += "| Component ID | Language | Mentions | Existing | Existence Ratio |\n"
        report += "|-------------|----------|----------|----------|----------------|\n"
        
        for comp_id, result in sorted_results:
            report += f"| {comp_id} | {result.language} | {result.total_mentions} | {result.existing_mentions} | {result.existence_ratio:.2%} |\n"
        
        # Hallucination Cases
        report += "\n## Hallucination Cases (Components That Don't Exist)\n\n"
        hallucinations = []
        for comp_id, result in results.items():
            for cm in result.mentioned_components:
                if not cm.exists:
                    hallucinations.append((comp_id, result.language, cm.name))
        
        if hallucinations:
            report += "| Component ID | Language | Hallucinated Component |\n"
            report += "|-------------|----------|------------------------|\n"
            
            for comp_id, language, component_name in hallucinations[:20]:  # Limit to 20
                report += f"| {comp_id} | {language} | `{component_name}` |\n"
            
            if len(hallucinations) > 20:
                report += f"\n*... and {len(hallucinations) - 20} more hallucinations*\n"
        else:
            report += "*No hallucinations detected!* ✅\n"
        
        # Cross-file Reference Analysis
        report += "\n## Cross-file Reference Analysis\n\n"
        cross_file_refs = []
        for comp_id, result in results.items():
            for cm in result.mentioned_components:
                if cm.is_cross_file:
                    cross_file_refs.append((comp_id, result.language, cm.name, cm.file_path))
        
        if cross_file_refs:
            report += f"Found {len(cross_file_refs)} cross-file references, indicating good contextual awareness.\n\n"
            report += "| Component ID | Language | Referenced Component | Source File |\n"
            report += "|-------------|----------|---------------------|-------------|\n"
            
            for comp_id, language, ref_name, file_path in cross_file_refs[:15]:  # Limit to 15
                file_display = Path(file_path).name if file_path else "Unknown"
                report += f"| {comp_id} | {language} | `{ref_name}` | {file_display} |\n"
            
            if len(cross_file_refs) > 15:
                report += f"\n*... and {len(cross_file_refs) - 15} more cross-file references*\n"
        else:
            report += "*No cross-file references found.*\n"
        
        # Save markdown report
        md_output = output_dir / "truthfulness_evaluation_report.md"
        with open(md_output, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Saved markdown report to {md_output}")


def main():
    """Main entry point for truthfulness evaluation"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Evaluate truthfulness of generated docstrings'
    )
    parser.add_argument(
        '--writer-dir',
        type=str,
        default=str(DATA_ROOT / 'intermediate' / 'agent_output' / 'writer'),
        help='Directory containing writer output JSON files'
    )
    parser.add_argument(
        '--navigator-dir',
        type=str,
        default=str(DATA_ROOT / 'intermediate' / 'navigator_output'),
        help='Directory containing navigator output (DAGs, components)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=str(DATA_ROOT / 'validation' / 'truthfulness'),
        help='Directory to save evaluation results'
    )
    parser.add_argument(
        '--llm-mode',
        type=str,
        default='llama_cpp',
        help='Local LLM mode for component extraction. Only llama_cpp is supported.'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        default=False,
        help='Disable LLM and use regex-based extraction only (faster but less accurate)'
    )
    
    args = parser.parse_args()
    
    # Use LLM by default unless --no-llm is specified
    use_llm = not args.no_llm
    
    # Resolve paths
    writer_dir = Path(args.writer_dir)
    if not writer_dir.is_absolute():
        writer_dir = project_root / writer_dir

    navigator_dir = Path(args.navigator_dir)
    if not navigator_dir.is_absolute():
        navigator_dir = project_root / navigator_dir

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    
    print("=" * 60)
    print("Docstring Truthfulness Evaluation")
    print("=" * 60)
    print(f"Writer output: {writer_dir}")
    print(f"Navigator output: {navigator_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Use LLM: {use_llm}")
    if use_llm:
        print("LLM Mode: llama_cpp (local model)")
    else:
        print("LLM Mode: Regex-based extraction only")
    print("=" * 60)
    print()
    
    # Create evaluator
    evaluator = TruthfulnessEvaluator(
        writer_output_dir=str(writer_dir),
        navigator_output_dir=str(navigator_dir),
        use_llm=use_llm,
        llm_mode=args.llm_mode
    )
    
    # Run evaluation
    print("Starting evaluation...")
    results = evaluator.evaluate_all()
    
    print(f"\n✅ Evaluated {len(results)} docstrings")
    
    # Generate report
    print("\nGenerating report...")
    evaluator.generate_report(results, output_dir)
    
    print(f"\n✅ Reports saved to {output_dir}")
    print("\nEvaluation complete!")


if __name__ == "__main__":
    main()
