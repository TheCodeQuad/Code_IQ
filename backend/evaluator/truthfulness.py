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

# Check for LLM configuration
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Install with: pip install google-generativeai")

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
        llm_mode: str = "llama_cpp"  # "gemini" or "llama_cpp"
    ):
        """
        Initialize the truthfulness evaluator.
        
        Args:
            writer_output_dir: Directory containing writer agent output JSON files
            navigator_output_dir: Directory containing navigator output (DAGs, components)
            use_llm: Whether to use LLM for component extraction (fallback to regex)
            llm_mode: Which LLM to use ("gemini" or "llama_cpp")
        """
        self.writer_output_dir = Path(writer_output_dir)
        self.navigator_output_dir = Path(navigator_output_dir)
        self.use_llm = use_llm
        self.llm_mode = llm_mode
        
        # Initialize LLM if available
        self.llm = None
        if self.use_llm:
            self._initialize_llm()
        
        # Load component database from navigator output
        self.component_db = self._load_component_database()
        
        logger.info(f"Loaded {len(self.component_db)} components from navigator output")
    
    def _initialize_llm(self):
        """Initialize the LLM for component extraction"""
        if self.llm_mode == "gemini" and GEMINI_AVAILABLE:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not set. Falling back to regex extraction.")
                self.use_llm = False
                return
            
            genai.configure(api_key=api_key)
            self.llm = genai.GenerativeModel("gemini-2.0-flash")
            logger.info("Initialized Gemini API for component extraction")
        
        elif self.llm_mode == "llama_cpp" and LLAMA_CPP_AVAILABLE:
            # Load local GGUF model
            model_path = project_root / "models" / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
            
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
            logger.info(f"Initialized llama.cpp with model: {model_path.name}")
        
        else:
            logger.warning(f"LLM mode '{self.llm_mode}' not available. Using regex extraction.")
            self.use_llm = False
    
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
            if self.llm_mode == "gemini":
                return self._extract_with_gemini(docstring, language)
            elif self.llm_mode == "llama_cpp":
                return self._extract_with_llama(docstring, language)
        
        # Fallback to regex-based extraction
        return self._extract_with_regex(docstring, language)
    
    def _extract_with_gemini(self, docstring: str, language: str) -> List[str]:
        """Extract components using Gemini API"""
        prompt = f"""
Extract all non-common code components (classes, methods, functions) mentioned in 
the following {language} docstring.

Ignore common standard library components (e.g., List, Dict, String, Array).
Ignore example code if present.
Focus on custom/user-defined components.

Return only a Python list of strings with exact names.
If no components are mentioned, return an empty list.

Docstring:
```
{docstring}
```

Format your response as a Python list wrapped in XML tags:
<python_list>["ComponentA", "method_b", "function_c"]</python_list>
"""
        
        try:
            response = self.llm.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract list from XML tags
            match = re.search(r'<python_list>(.*?)</python_list>', response_text, re.DOTALL)
            if match:
                list_str = match.group(1)
                try:
                    components = eval(list_str)
                    if isinstance(components, list):
                        return components
                except:
                    components = re.findall(r'"([^"]*)"', list_str)
                    return components
            
            # Fallback
            match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if match:
                list_str = match.group(0)
                try:
                    components = eval(list_str)
                    if isinstance(components, list):
                        return components
                except:
                    components = re.findall(r'"([^"]*)"', list_str)
                    return components
        
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
        
        # Fallback to regex
        return self._extract_with_regex(docstring, language)
    
    def _extract_with_llama(self, docstring: str, language: str) -> List[str]:
        """Extract components using llama.cpp"""
        prompt = f"""Extract all custom code components (classes, methods, functions) mentioned in this {language} docstring.
Ignore standard library components. Return only a JSON array of strings.

Docstring: {docstring}

Response (JSON array only):"""
        
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
                        return components
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
        Does NOT extract regular English words to avoid false positives.
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
        
        # 3. Language-specific patterns for method calls
        if language == "python":
            # self.method_name or obj.method_name
            method_pattern = r'\.([a-z_][a-z0-9_]*)\b'
            method_matches = re.findall(method_pattern, docstring)
            components.extend(method_matches)
        
        elif language in ["javascript", "typescript"]:
            # this.methodName or object.methodName
            method_pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]*)\b'
            method_matches = re.findall(method_pattern, docstring)
            components.extend(method_matches)
        
        elif language == "java":
            # ClassName.methodName or object.methodName
            method_pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]*)\b'
            method_matches = re.findall(method_pattern, docstring)
            components.extend(method_matches)
        
        # 4. Filter out common/standard library names and regular words
        common_words = {
            # Common programming terms (NOT component names)
            'error', 'string', 'number', 'boolean', 'array', 'object',
            'true', 'false', 'null', 'undefined', 'void', 'return',
            'value', 'result', 'data', 'input', 'output', 'type',
            # Common English words that might be capitalized
            'the', 'and', 'for', 'with', 'this', 'that', 'from', 'into',
            'operation', 'function', 'method', 'class', 'module',
            # Standard library (Python)
            'list', 'dict', 'set', 'tuple', 'str', 'int', 'float',
            'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
            # Standard library (JavaScript)
            'console', 'log', 'warn', 'error', 'push', 'pop', 'shift',
            'slice', 'splice', 'join', 'split', 'trim', 'toLowerCase',
            # Standard library (Java)
            'System', 'out', 'println', 'toString', 'equals', 'hashCode'
        }
        
        # Remove duplicates and filter
        components = list(set([
            c for c in components 
            if c.lower() not in common_words 
            and len(c) > 2  # At least 3 characters
            and not c.isdigit()  # Not just numbers
        ]))
        
        return components
    
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
        
        return exists, is_cross_file, component_type, found_file_path
    
    def evaluate_docstring(
        self,
        component_id: str,
        docstring: str,
        file_path: str,
        language: str
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
        # Extract mentioned components
        mentioned_components = self.extract_components_from_docstring(docstring, language)
        
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
        existence_ratio = existing_mentions / total_mentions if total_mentions > 0 else 0.0
        hallucination_rate = (total_mentions - existing_mentions) / total_mentions if total_mentions > 0 else 0.0
        
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
    
    def evaluate_all(self) -> Dict[str, TruthfulnessResult]:
        """
        Evaluate all docstrings in the writer output directory.
        
        Returns:
            Dictionary mapping component_id to TruthfulnessResult
        """
        results = {}
        
        # Load all writer output files
        writer_files = list(self.writer_output_dir.glob("*.json"))
        
        logger.info(f"Found {len(writer_files)} writer output files")
        
        for writer_file in tqdm(writer_files, desc="Evaluating docstrings"):
            try:
                with open(writer_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                component_id = data.get("component_id", writer_file.stem)
                docstring = data.get("docstring", "")
                language = data.get("language", "python")
                
                # Extract file path from component location if available
                file_path = data.get("file_path", "")
                if not file_path and "location" in data:
                    location = data["location"]
                    if isinstance(location, dict):
                        file_path = location.get("file_path", "")
                
                # Clean docstring (remove <DOCSTRING> tags if present)
                docstring = re.sub(r'</?DOCSTRING>', '', docstring).strip()
                
                if docstring:
                    result = self.evaluate_docstring(
                        component_id=component_id,
                        docstring=docstring,
                        file_path=file_path,
                        language=language
                    )
                    results[component_id] = result
            
            except Exception as e:
                logger.error(f"Error processing {writer_file}: {e}")
        
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
        choices=['gemini', 'llama_cpp'],
        default='llama_cpp',
        help='Which LLM to use for component extraction. Defaults to llama_cpp (local model).'
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
        print(f"LLM Mode: {args.llm_mode} (local model)")
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
