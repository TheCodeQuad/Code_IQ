"""
Docstring Inserter Utility — Language-Agnostic Engine

Inserts generated docstrings into source code files at the correct component locations.
Supports dependency-based ordering and multiple programming languages.

Supported languages:
  - Python: Triple-quoted strings (Google, NumPy, RST styles)
  - JavaScript / TypeScript: JSDoc /** */ comments (placed before definition)
  - Java: JavaDoc /** */ comments (placed before definition)
  - Go / Rust: Line comments (placed before definition)

Key features:
  1. Language-agnostic insertion with per-language configuration
  2. Dependency-based component ordering (via topo module)
  3. Continuous (real-time) and batch insertion modes
  4. Proper docstring position detection per language
  5. Existing docstring skip/overwrite logic with word-count threshold
  6. Line offset tracking for sequential insertions
  7. Backup support before modifications
  8. LLM response extraction and cleaning
"""
import re
import json
import random
import textwrap
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from backend.utils.logger import get_logger
from backend.utils.file_handler import FileHandler

logger = get_logger(__name__)


# ============================================================================
#  Language Configuration System
# ============================================================================

@dataclass
class LanguageConfig:
    """
    Language-specific configuration for docstring insertion.

    Controls *where* the docstring is placed relative to the definition,
    *how* it is formatted, and *how* existing docstrings are detected.
    """
    name: str                          # e.g. 'python', 'javascript'
    extensions: List[str]              # e.g. ['.py']

    # -- positioning ----------------------------------------------------------
    # 'inside' → Python-style: docstring as first statement inside the body
    # 'before' → JSDoc/JavaDoc-style: comment block *before* the definition
    docstring_position: str = "inside"

    # -- comment syntax -------------------------------------------------------
    doc_open: str = '\"\"\"'           # opening delimiter
    doc_close: str = '\"\"\"'          # closing delimiter
    doc_line_prefix: str = ""          # prefix for each interior line
    single_line_template: str = "{indent}{open}{text}{close}"  # 1-line fmt

    # -- definition detection -------------------------------------------------
    definition_end_chars: List[str] = field(default_factory=lambda: [':'])
    skip_decorators: bool = True       # skip @decorator lines when searching
    annotation_prefix: str = "@"       # Java/TS annotations

    # -- body indentation (relative to definition) ----------------------------
    body_indent_offset: int = 4        # Python: 4, C-style: 0

    # -- existing docstring detection -----------------------------------------
    existing_open_markers: List[str] = field(default_factory=lambda: ['\"\"\"', "'''"])
    existing_close_markers: List[str] = field(default_factory=lambda: ['\"\"\"', "'''"])


# Pre-built configs for supported languages
_PYTHON_CONFIG = LanguageConfig(
    name="python",
    extensions=[".py"],
    docstring_position="inside",
    doc_open='\"\"\"',
    doc_close='\"\"\"',
    doc_line_prefix="",
    single_line_template='{indent}\"\"\"{text}\"\"\"',
    definition_end_chars=[":"],
    body_indent_offset=4,
    existing_open_markers=['\"\"\"', "'''"],
    existing_close_markers=['\"\"\"', "'''"],
)

_JAVASCRIPT_CONFIG = LanguageConfig(
    name="javascript",
    extensions=[".js", ".jsx", ".mjs", ".cjs"],
    docstring_position="before",
    doc_open="/**",
    doc_close=" */",
    doc_line_prefix=" * ",
    single_line_template="{indent}/** {text} */",
    definition_end_chars=["{"],
    annotation_prefix="@",
    body_indent_offset=0,
    existing_open_markers=["/**"],
    existing_close_markers=["*/"],
)

_TYPESCRIPT_CONFIG = LanguageConfig(
    name="typescript",
    extensions=[".ts", ".tsx"],
    docstring_position="before",
    doc_open="/**",
    doc_close=" */",
    doc_line_prefix=" * ",
    single_line_template="{indent}/** {text} */",
    definition_end_chars=["{"],
    annotation_prefix="@",
    body_indent_offset=0,
    existing_open_markers=["/**"],
    existing_close_markers=["*/"],
)

_JAVA_CONFIG = LanguageConfig(
    name="java",
    extensions=[".java"],
    docstring_position="before",
    doc_open="/**",
    doc_close=" */",
    doc_line_prefix=" * ",
    single_line_template="{indent}/** {text} */",
    definition_end_chars=["{"],
    annotation_prefix="@",
    skip_decorators=True,
    body_indent_offset=0,
    existing_open_markers=["/**"],
    existing_close_markers=["*/"],
)

_GO_CONFIG = LanguageConfig(
    name="go",
    extensions=[".go"],
    docstring_position="before",
    doc_open="//",
    doc_close="",
    doc_line_prefix="// ",
    single_line_template="{indent}// {text}",
    definition_end_chars=["{"],
    body_indent_offset=0,
    existing_open_markers=["//"],
    existing_close_markers=[],  # line comments end at newline
)

_RUST_CONFIG = LanguageConfig(
    name="rust",
    extensions=[".rs"],
    docstring_position="before",
    doc_open="///",
    doc_close="",
    doc_line_prefix="/// ",
    single_line_template="{indent}/// {text}",
    definition_end_chars=["{"],
    body_indent_offset=0,
    existing_open_markers=["///"],
    existing_close_markers=[],
)

_CPP_CONFIG = LanguageConfig(
    name="cpp",
    extensions=[".cpp", ".cc", ".cxx", ".c++", ".hpp", ".h"],
    docstring_position="before",
    doc_open="/**",
    doc_close=" */",
    doc_line_prefix=" * ",
    single_line_template="{indent}/** {text} */",
    definition_end_chars=["{"],
    body_indent_offset=0,
    existing_open_markers=["/**"],
    existing_close_markers=["*/"],
)

_CSHARP_CONFIG = LanguageConfig(
    name="csharp",
    extensions=[".cs"],
    docstring_position="before",
    doc_open="/// <summary>",
    doc_close="/// </summary>",
    doc_line_prefix="/// ",
    single_line_template="{indent}/// <summary>{text}</summary>",
    definition_end_chars=["{"],
    annotation_prefix="[",
    body_indent_offset=0,
    existing_open_markers=["/// <summary>", "///<summary>"],
    existing_close_markers=["/// </summary>", "///</summary>"],
)

# Master registry: extension → LanguageConfig
LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = {}
for _cfg in [
    _PYTHON_CONFIG, _JAVASCRIPT_CONFIG, _TYPESCRIPT_CONFIG, _JAVA_CONFIG,
    _GO_CONFIG, _RUST_CONFIG, _CPP_CONFIG, _CSHARP_CONFIG,
]:
    for _ext in _cfg.extensions:
        LANGUAGE_CONFIGS[_ext] = _cfg

# Name → LanguageConfig (for lookup by language identifier)
LANGUAGE_CONFIGS_BY_NAME: Dict[str, LanguageConfig] = {
    cfg.name: cfg for cfg in [
        _PYTHON_CONFIG, _JAVASCRIPT_CONFIG, _TYPESCRIPT_CONFIG, _JAVA_CONFIG,
        _GO_CONFIG, _RUST_CONFIG, _CPP_CONFIG, _CSHARP_CONFIG,
    ]
}


def get_language_config(language_or_path: str) -> LanguageConfig:
    """
    Resolve a LanguageConfig from a language name *or* a file path.

    Falls back to Python if the language/extension is unknown.
    """
    # Try as language name first
    if language_or_path in LANGUAGE_CONFIGS_BY_NAME:
        return LANGUAGE_CONFIGS_BY_NAME[language_or_path]

    # Try as file extension
    ext = Path(language_or_path).suffix.lower() if '.' in language_or_path else None
    if ext and ext in LANGUAGE_CONFIGS:
        return LANGUAGE_CONFIGS[ext]

    return _PYTHON_CONFIG  # safe default


# ============================================================================
#  Data Classes
# ============================================================================

class DocstringStyle(Enum):
    """Supported docstring styles"""
    GOOGLE = "google"
    NUMPY = "numpy"
    RST = "rst"


@dataclass
class InsertionPoint:
    """Represents where a docstring should be inserted"""
    component_id: str
    file_path: str
    start_line: int  # Line where component starts (1-indexed)
    component_type: str  # class, function, method
    docstring: str
    has_existing_docstring: bool = False
    existing_docstring_lines: Tuple[int, int] = (0, 0)  # start, end lines if exists
    language: str = "python"  # Programming language detected from file extension


@dataclass
class InsertionResult:
    """Result of a docstring insertion"""
    component_id: str
    file_path: str
    success: bool
    action: str  # 'inserted', 'replaced', 'skipped'
    message: str = ""


class DocstringInserter:
    """
    Inserts generated docstrings into Python source files.
    
    Features:
    - Detects existing docstrings and can replace or skip them
    - Handles proper indentation based on component context
    - Supports classes, functions, and methods
    - Creates backups before modification
    - Supports both batch and continuous (single component) insertion
    """
    
    def __init__(
        self,
        writer_output_dir: Optional[Path] = None,
        component_data_file: Optional[Path] = None,
        backup: bool = True,
        replace_existing: bool = False
    ):
        """
        Initialize the docstring inserter.
        
        Args:
            writer_output_dir: Directory containing writer output JSON files (for batch mode)
            component_data_file: Path to component data JSON (reader output or IR)
            backup: Whether to create backups before modifying files
            replace_existing: Whether to replace existing docstrings
        """
        self.writer_output_dir = Path(writer_output_dir) if writer_output_dir else None
        self.component_data_file = Path(component_data_file) if component_data_file else None
        self.backup = backup
        self.replace_existing = replace_existing
        self.file_handler = FileHandler()
        
        # Component data (loaded from reader output or IR)
        self.component_data: Dict[str, Any] = {}
        if self.component_data_file:
            self._load_component_data()
        
        # Track which files have been backed up (avoid multiple backups)
        self.backed_up_files: set = set()
        
        # Track line offsets per file for continuous insertion mode
        # When we insert a docstring, subsequent component line numbers shift
        self.line_offsets: Dict[str, Dict[int, int]] = {}  # {file_path: {original_line: offset}}
        
        # Cache for file contents (to batch edits per file)
        self.file_cache: Dict[str, List[str]] = {}
        self.file_modifications: Dict[str, List[InsertionPoint]] = {}
    
    def _get_adjusted_line(self, file_path: str, original_line: int) -> int:
        """
        Get the adjusted line number accounting for previous insertions.
        
        When we insert docstrings, line numbers shift. This tracks the cumulative
        offset so subsequent insertions target the correct line.
        """
        if file_path not in self.line_offsets:
            return original_line
        
        # Sum up all offsets for lines before this one
        total_offset = sum(
            offset for line, offset in self.line_offsets[file_path].items()
            if line < original_line
        )
        
        return original_line + total_offset
    
    def _record_line_offset(self, file_path: str, at_line: int, offset: int):
        """Record that an insertion added 'offset' lines at 'at_line'"""
        if file_path not in self.line_offsets:
            self.line_offsets[file_path] = {}
        self.line_offsets[file_path][at_line] = offset
    
    def reset_line_tracking(self, file_path: Optional[str] = None):
        """Reset line offset tracking (call when starting a new file or session)"""
        if file_path:
            self.line_offsets.pop(file_path, None)
        else:
            self.line_offsets.clear()
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension.

        Uses the LanguageConfig registry for consistent mapping.

        Args:
            file_path: Path to the source file

        Returns:
            str: Language identifier (python, javascript, java, etc.)
        """
        cfg = get_language_config(file_path)
        return cfg.name

    def _get_lang_config(self, language: str) -> LanguageConfig:
        """Get the LanguageConfig for a given language identifier."""
        return get_language_config(language)
    
    def _load_component_data(self):
        """Load component data containing component locations"""
        if self.component_data_file and self.component_data_file.exists():
            self.component_data = self.file_handler.read_json(self.component_data_file)
            logger.info(f"Loaded component data with {len(self.component_data)} components")
        else:
            logger.warning(f"Component data file not found: {self.component_data_file}")
    
    # ========== CONTINUOUS INSERTION MODE ==========
    
    def insert_single_docstring(
        self,
        component_id: str,
        docstring: str,
        file_path: str,
        start_line: int,
        component_type: str = "function",
        has_existing_docstring: bool = False,
        language: Optional[str] = None
    ) -> InsertionResult:
        """
        Insert a single docstring for one component (for continuous pipeline mode).
        
        This method is called by the pipeline after each component is processed
        by the writer agent, allowing real-time docstring insertion.
        
        Args:
            component_id: Unique identifier for the component
            docstring: The generated docstring text
            file_path: Absolute path to the source file
            start_line: Line number where component definition starts (1-indexed)
            component_type: Type of component (class, function, method)
            has_existing_docstring: Whether the component already has a docstring
            
        Returns:
            InsertionResult with success status and action taken
        """
        if not docstring or not docstring.strip():
            return InsertionResult(
                component_id=component_id,
                file_path=file_path,
                success=False,
                action='skipped',
                message="Empty docstring provided"
            )
        
        full_path = Path(file_path)
        
        if not full_path.exists():
            return InsertionResult(
                component_id=component_id,
                file_path=file_path,
                success=False,
                action='skipped',
                message=f"File not found: {full_path}"
            )
        
        try:
            # Read current file content
            content = self.file_handler.read_file(full_path)
            lines = content.split('\n')
            
            # Create backup only once per file
            if self.backup and file_path not in self.backed_up_files:
                backup_path = full_path.with_suffix(full_path.suffix + '.bak')
                self.file_handler.write_file(backup_path, content)
                self.backed_up_files.add(file_path)
            
            # Adjust line number for previous insertions in this file
            adjusted_line = self._get_adjusted_line(file_path, start_line)
            
            # Detect language if not provided
            if not language:
                language = self._detect_language(file_path)
            
            # Find insertion position (pass language for proper docstring detection)
            insert_idx, existing_end_idx, base_indent = self._find_docstring_insert_position(
                lines, adjusted_line, component_type, language
            )
            
            has_existing = existing_end_idx > insert_idx
            
            # Format the new docstring with language-aware syntax
            docstring_lines = self._format_docstring(docstring, base_indent, component_type, language)
            
            # Calculate line offset for future insertions
            if has_existing:
                # Replace existing docstring
                old_docstring_lines = existing_end_idx - insert_idx
                new_docstring_lines = len(docstring_lines)
                line_offset = new_docstring_lines - old_docstring_lines
                lines = lines[:insert_idx] + docstring_lines + lines[existing_end_idx:]
                action = 'replaced'
            else:
                # Insert new docstring
                line_offset = len(docstring_lines)
                lines = lines[:insert_idx] + docstring_lines + lines[insert_idx:]
                action = 'inserted'
            
            # Record line offset for subsequent insertions in this file
            self._record_line_offset(file_path, start_line, line_offset)
            
            # Write modified content back immediately
            new_content = '\n'.join(lines)
            self.file_handler.write_file(full_path, new_content)
            
            logger.debug(f"Docstring {action} for {component_id} at line {insert_idx + 1}")
            
            return InsertionResult(
                component_id=component_id,
                file_path=file_path,
                success=True,
                action=action,
                message=f"Docstring {action} at line {insert_idx + 1}"
            )
            
        except Exception as e:
            logger.error(f"Error inserting docstring for {component_id}: {e}")
            return InsertionResult(
                component_id=component_id,
                file_path=file_path,
                success=False,
                action='error',
                message=str(e)
            )
    
    def insert_for_component(
        self,
        component: Any,
        docstring_data: Dict[str, Any]
    ) -> InsertionResult:
        """
        Insert docstring for a CodeComponent object (convenience method for pipeline).
        
        Args:
            component: CodeComponent object with location info
            docstring_data: Writer output dict containing 'docstring' key
            
        Returns:
            InsertionResult with success status
        """
        # Extract location from component
        if hasattr(component, 'location') and component.location:
            file_path = component.location.file_path
            start_line = component.location.start_line
        elif hasattr(component, 'file_path'):
            file_path = component.file_path
            start_line = getattr(component, 'start_line', 0)
        else:
            return InsertionResult(
                component_id=getattr(component, 'id', 'unknown'),
                file_path='unknown',
                success=False,
                action='skipped',
                message="Component missing location info"
            )
        
        # Get component type - handle both string and enum types
        comp_type = getattr(component, 'type', 'function')
        if hasattr(comp_type, 'value'):
            comp_type = comp_type.value
        
        return self.insert_single_docstring(
            component_id=getattr(component, 'id', 'unknown'),
            docstring=docstring_data.get('docstring', ''),
            file_path=file_path,
            start_line=start_line,
            component_type=comp_type,
            has_existing_docstring=bool(getattr(component, 'existing_docstring', None))
        )
    
    # ========== BATCH INSERTION MODE ==========
    
    def load_writer_outputs(self) -> Dict[str, Any]:
        """Load all writer output files and merge them"""
        all_docstrings = {}
        
        if not self.writer_output_dir.exists():
            logger.warning(f"Writer output directory not found: {self.writer_output_dir}")
            return all_docstrings
        
        for json_file in self.writer_output_dir.glob("*_writer_output.json"):
            try:
                data = self.file_handler.read_json(json_file)
                all_docstrings.update(data)
                logger.info(f"Loaded {len(data)} docstrings from {json_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")
        
        return all_docstrings
    
    def prepare_insertions(
        self,
        docstrings: Dict[str, Any]
    ) -> List[InsertionPoint]:
        """
        Prepare insertion points by matching docstrings with component locations.
        
        Args:
            docstrings: Dictionary of component_id -> docstring data
            
        Returns:
            List of InsertionPoint objects sorted by file and line number
        """
        insertion_points = []
        
        for component_id, doc_data in docstrings.items():
            # Get component location from component data (reader output)
            if component_id not in self.component_data:
                logger.debug(f"Component not in data: {component_id}")
                continue
            
            component = self.component_data[component_id]
            component_type = component.get('type', 'function')
            
            # Skip global variables - they don't have docstrings
            if component_type == 'global_variable':
                continue
            
            # Get location info - support both reader output and IR formats
            location = component.get('location', {})
            if location:
                # Reader output format: location.file_path, location.start_line
                file_path = location.get('file_path', '')
                start_line = location.get('start_line', 0)
            else:
                # IR format: file_path, start_line at top level
                file_path = component.get('file_path', '')
                start_line = component.get('start_line', 0)
            
            has_docstring = component.get('has_docstring', False) or bool(component.get('existing_docstring'))
            
            if not file_path or start_line == 0:
                logger.debug(f"Missing location for: {component_id}")
                continue
            
            # Get the docstring text
            docstring = doc_data.get('docstring', '')
            if not docstring:
                continue
            
            insertion_points.append(InsertionPoint(
                component_id=component_id,
                file_path=file_path,
                start_line=start_line,
                component_type=component_type,
                docstring=docstring,
                has_existing_docstring=has_docstring,
                language=self._detect_language(file_path)
            ))
        
        # Sort by file path, then by line number (descending for bottom-up insertion)
        insertion_points.sort(key=lambda x: (x.file_path, -x.start_line))
        
        logger.info(f"Prepared {len(insertion_points)} insertion points")
        return insertion_points
    
    # ========== DOCSTRING EXTRACTION AND CLEANING ==========
    
    def extract_docstring(self, response: str) -> str:
        """Extract the docstring from the LLM response.
        
        Handles multiple tag formats and extraction strategies.
        
        Args:
            response: The full response from the LLM containing the docstring between XML tags
            
        Returns:
            str: The extracted docstring, or empty string if extraction fails
        """
        logger.info(f"LLM Response length: {len(response)} chars")
        logger.info(f"LLM Response preview: {response[:500]}...")
        
        # Strategy 1: Try standard DOCSTRING tags
        for start_tag, end_tag in [
            ("<DOCSTRING>", "</DOCSTRING>"),
            ("<docstring>", "</docstring>"),
            ("<Docstring>", "</Docstring>"),
        ]:
            try:
                response_lower = response.lower()
                start_tag_lower = start_tag.lower()
                end_tag_lower = end_tag.lower()
                
                start_idx = response_lower.index(start_tag_lower) + len(start_tag_lower)
                end_idx = response_lower.index(end_tag_lower)
                
                docstring = response[start_idx:end_idx].strip()
                
                if docstring and len(docstring.split()) >= 2:  # At least 2 words
                    logger.info(f"Extracted docstring from {start_tag} ({len(docstring)} chars): {docstring[:200]}...")
                    return docstring
                    
            except (ValueError, IndexError):
                continue
        
        # Strategy 2: Try alternative tag formats (summary, describe, etc.)
        tag_alternatives = [
            ("<summary>", "</summary>"),
            ("<SUMMARY>", "</SUMMARY>"),
            ("<describe>", "</describe>"),
            ("<DESCRIBE>", "</DESCRIBE>"),
            ("<description>", "</description>"),
            ("<DESCRIPTION>", "</DESCRIPTION>"),
        ]
        
        for start_tag, end_tag in tag_alternatives:
            try:
                response_lower = response.lower()
                start_tag_lower = start_tag.lower()
                end_tag_lower = end_tag.lower()
                
                start_idx = response_lower.index(start_tag_lower) + len(start_tag_lower)
                end_idx = response_lower.index(end_tag_lower)
                
                docstring = response[start_idx:end_idx].strip()
                
                if docstring and len(docstring.split()) >= 2:
                    logger.info(f"Extracted docstring from {start_tag} ({len(docstring)} chars): {docstring[:200]}...")
                    return docstring
                    
            except (ValueError, IndexError):
                continue
        
        # Strategy 3: Try to find any content between angle brackets
        potential_extracts = re.findall(r'<[a-zA-Z_]+>(.*?)</[a-zA-Z_]+>', response, re.DOTALL)
        for extract in potential_extracts:
            extract_clean = extract.strip()
            # Filter out code blocks and formatting artifacts
            if extract_clean and len(extract_clean.split()) >= 2 and not extract_clean.startswith(('<', '{')):
                logger.info(f"Extracted docstring from loose tag ({len(extract_clean)} chars): {extract_clean[:200]}...")
                return extract_clean
        
        # No valid extraction found
        logger.warning(f"Could not extract docstring. Full response:\n{response[:1000]}")
        return ""
    
    def _clean_thinking_tokens(self, text: str) -> str:
        """Remove thinking tokens and other LLM artifacts from the response.
        
        Args:
            text: Raw text that may contain <think>...</think> blocks
            
        Returns:
            str: Cleaned text with thinking tokens removed
        """
        # Remove <think>...</think> blocks (greedy, handles multiline)
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any remaining XML-like artifacts that aren't docstring tags
        cleaned = re.sub(r'</?(?!DOCSTRING|docstring)[a-zA-Z_]+>', '', cleaned)
        
        return cleaned.strip()
    
    def _clean_docstring_artifacts(self, docstring: str) -> str:
        """Clean artifacts and formatting issues from extracted docstring.
        
        Args:
            docstring: Raw extracted docstring
            
        Returns:
            str: Cleaned docstring ready for insertion
        """
        # Remove any remaining thinking tokens
        cleaned = self._clean_thinking_tokens(docstring)
        
        # Remove triple quotes if LLM included them (insertion will add proper quotes)
        cleaned = re.sub(r'^[\s]*["\'][\s]*["\'][\s]*["\']\s*', '', cleaned)  # Start
        cleaned = re.sub(r'\s*["\'][\s]*["\'][\s]*["\']\s*$', '', cleaned)  # End
        
        # Normalize whitespace
        lines = cleaned.split('\n')
        # Remove completely empty lines at start and end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)
    
    # ========== UTILITIES ==========
    
    def _get_indentation(self, line: str) -> str:
        """Extract leading whitespace from a line.
        
        Args:
            line: A line of source code
            
        Returns:
            str: The leading whitespace (spaces/tabs) from the line
        """
        return line[:len(line) - len(line.lstrip())]
    
    def _format_docstring(
        self,
        docstring: str,
        base_indent: str,
        component_type: str,
        language: str = "python"
    ) -> List[str]:
        """
        Format docstring with proper indentation and language-specific syntax.

        Uses the LanguageConfig registry to determine comment style, indentation,
        and delimiter placement for each target language.

        Supports:
        - Python: Triple-quoted strings (``\"\"\"``)
        - JavaScript / TypeScript / Java / C++ / C#: Block comments (``/** */``)
        - Go / Rust: Doc-line comments (``//`` / ``///``)

        Args:
            docstring: Raw docstring text
            base_indent: Base indentation of the component *definition* line
            component_type: Type of component (class, function, method)
            language: Programming language identifier

        Returns:
            List of formatted docstring lines ready for splicing into the file.
        """
        cfg = self._get_lang_config(language)
        content_lines = docstring.strip().split('\n')

        # Compute effective indent:
        #   Python ('inside'): body indent = definition indent + offset (4)
        #   C-style ('before'): same indent as the definition
        if cfg.docstring_position == "inside":
            indent = base_indent + (" " * cfg.body_indent_offset)
        else:
            indent = base_indent

        # Dispatch to the appropriate formatter
        if cfg.name == "python":
            return self._format_python_docstring(content_lines, indent)
        elif cfg.doc_open.startswith("/**"):
            return self._format_block_comment(content_lines, indent, cfg)
        elif cfg.doc_open.startswith("///"):
            return self._format_rust_doc_comment(content_lines, indent, cfg)
        elif cfg.doc_open.startswith("//"):
            return self._format_line_comment(content_lines, indent, cfg)
        elif cfg.doc_open.startswith("/// <summary>"):
            return self._format_csharp_xml_comment(content_lines, indent, cfg)
        else:
            return self._format_python_docstring(content_lines, indent)

    # -- per-language formatters -----------------------------------------------

    def _format_python_docstring(self, lines: List[str], indent: str) -> List[str]:
        """Format docstring as Python triple-quoted string."""
        if len(lines) == 1:
            return [f'{indent}\"\"\"{lines[0]}\"\"\"']
        formatted = [f'{indent}\"\"\"']
        for line in lines:
            if line.strip():
                formatted.append(f'{indent}{line}')
            else:
                formatted.append('')
        formatted.append(f'{indent}\"\"\"')
        return formatted

    def _format_block_comment(
        self, lines: List[str], indent: str, cfg: LanguageConfig
    ) -> List[str]:
        """Format docstring as /** */ block comment (JSDoc / JavaDoc / Doxygen)."""
        if len(lines) == 1:
            return [cfg.single_line_template.format(indent=indent, open=cfg.doc_open, text=lines[0], close=cfg.doc_close)]
        formatted = [f'{indent}{cfg.doc_open}']
        for line in lines:
            if line.strip():
                formatted.append(f'{indent}{cfg.doc_line_prefix}{line}')
            else:
                formatted.append(f'{indent}{cfg.doc_line_prefix.rstrip()}')
        formatted.append(f'{indent}{cfg.doc_close}')
        return formatted

    def _format_rust_doc_comment(
        self, lines: List[str], indent: str, cfg: LanguageConfig
    ) -> List[str]:
        """Format docstring as Rust-style ``///`` doc comments."""
        formatted = []
        for line in lines:
            if line.strip():
                formatted.append(f'{indent}{cfg.doc_line_prefix}{line}')
            else:
                formatted.append(f'{indent}{cfg.doc_open}')
        return formatted

    def _format_line_comment(
        self, lines: List[str], indent: str, cfg: LanguageConfig
    ) -> List[str]:
        """Format docstring as line comments (Go ``//``, Ruby ``#``, etc.)."""
        formatted = []
        for line in lines:
            if line.strip():
                formatted.append(f'{indent}{cfg.doc_line_prefix}{line}')
            else:
                formatted.append('')  # preserve blank lines
        return formatted

    def _format_csharp_xml_comment(
        self, lines: List[str], indent: str, cfg: LanguageConfig
    ) -> List[str]:
        """Format docstring as C# XML documentation comments (``/// <summary>``)."""
        formatted = [f'{indent}/// <summary>']
        for line in lines:
            if line.strip():
                formatted.append(f'{indent}/// {line}')
            else:
                formatted.append(f'{indent}///')
        formatted.append(f'{indent}/// </summary>')
        return formatted

    # -- definition-end detection ----------------------------------------------

    def _find_definition_end(
        self, lines: List[str], start_idx: int, cfg: LanguageConfig
    ) -> int:
        """
        Find the line where the component header ends.

        Handles multi-line definitions by tracking parenthesis / bracket nesting
        and searching for the language-specific end character (``:``, ``{``, etc.).

        Returns the 0-indexed line number of the *last* line of the header.
        """
        end_chars = set(cfg.definition_end_chars)
        paren_depth = 0
        idx = start_idx

        while idx < len(lines):
            line = lines[idx]
            for ch in line:
                if ch in '([':
                    paren_depth += 1
                elif ch in ')]':
                    paren_depth = max(paren_depth - 1, 0)

            # Only match end chars when parentheses are closed
            if paren_depth == 0:
                for ec in end_chars:
                    if ec in line:
                        return idx
            idx += 1

        return min(start_idx, len(lines) - 1)

    # -- insertion position (language-aware) ------------------------------------

    def _find_docstring_insert_position(
        self,
        lines: List[str],
        start_line: int,
        component_type: str,
        language: str = "python"
    ) -> Tuple[int, int, str]:
        """
        Find where to insert/replace a docstring in source code.

        Correctly handles the two paradigms:
        - **Python** (``docstring_position='inside'``): docstring is the first
          statement *inside* the body, immediately after the ``:``.
        - **JS / TS / Java / …** (``docstring_position='before'``): doc-comment
          is placed *before* the definition (and before decorators/annotations).

        Args:
            lines: Source file split into individual lines.
            start_line: Component start line (1-indexed, from navigator).
            component_type: ``class``, ``function``, ``method``, etc.
            language: Language identifier used to look up ``LanguageConfig``.

        Returns:
            ``(insert_line_index, existing_end_index, base_indentation)``

            * ``insert_line_index`` – 0-indexed line where new docstring
              lines should start.
            * ``existing_end_index`` – 0-indexed exclusive end of the
              current docstring (== ``insert_line_index`` if none exists).
            * ``base_indentation`` – whitespace prefix of the definition line.
        """
        cfg = self._get_lang_config(language)
        start_idx = start_line - 1  # convert to 0-indexed

        if start_idx >= len(lines):
            return start_idx, start_idx, ""

        def_line = lines[start_idx]
        base_indent = self._get_indentation(def_line)

        # ==== Python-style: docstring goes INSIDE the body ====================
        if cfg.docstring_position == "inside":
            return self._find_inside_position(lines, start_idx, base_indent, cfg)

        # ==== C-style: doc-comment goes BEFORE the definition =================
        return self._find_before_position(lines, start_idx, base_indent, cfg)

    def _find_inside_position(
        self,
        lines: List[str],
        start_idx: int,
        base_indent: str,
        cfg: LanguageConfig
    ) -> Tuple[int, int, str]:
        """
        Locate insertion point for languages where the docstring lives inside
        the body (Python).

        Finds the end of the multi-line header (the ``:`` line), then checks
        if the first statement is already a triple-quoted string.
        """
        def_end = self._find_definition_end(lines, start_idx, cfg)
        insert_idx = def_end + 1

        if insert_idx >= len(lines):
            return insert_idx, insert_idx, base_indent

        next_line = lines[insert_idx].strip()
        existing_end_idx = insert_idx

        # Detect existing triple-quoted docstring
        for quote in cfg.existing_open_markers:
            if next_line.startswith(quote):
                # Single-line: """docstring"""
                if next_line.count(quote) >= 2 and len(next_line) > len(quote) * 2:
                    existing_end_idx = insert_idx + 1
                else:
                    # Multi-line – scan until closing quote
                    existing_end_idx = insert_idx + 1
                    while existing_end_idx < len(lines):
                        if quote in lines[existing_end_idx]:
                            existing_end_idx += 1
                            break
                        existing_end_idx += 1
                break  # first matching quote wins

        return insert_idx, existing_end_idx, base_indent

    def _find_before_position(
        self,
        lines: List[str],
        start_idx: int,
        base_indent: str,
        cfg: LanguageConfig
    ) -> Tuple[int, int, str]:
        """
        Locate insertion point for languages where the doc-comment goes
        before the definition (JS, TS, Java, C++, Go, Rust, C#).

        Scans upward from ``start_idx`` to find an existing doc-comment block.
        If found, returns its range for replacement.  If not, returns
        ``start_idx`` as both insert and end (so the comment is inserted
        right before the definition, pushing it down).

        Correctly skips blank lines and annotation/decorator lines when
        searching for existing comments.
        """
        check_idx = start_idx - 1

        # Skip blank lines and annotations/decorators between comment and def
        while check_idx >= 0:
            stripped = lines[check_idx].strip()
            if not stripped:
                check_idx -= 1
                continue
            # Skip Java/TS annotations (e.g. @Override, @Deprecated)
            if cfg.skip_decorators and stripped.startswith(cfg.annotation_prefix):
                check_idx -= 1
                continue
            break  # reached a non-blank, non-annotation line

        if check_idx < 0:
            return start_idx, start_idx, base_indent

        candidate = lines[check_idx].strip()

        # --- Block comments (/** … */) ---
        if cfg.existing_close_markers and any(
            candidate.endswith(m) for m in cfg.existing_close_markers
        ):
            # Found end of doc-comment – scan upward for opening marker
            comment_end_exclusive = check_idx + 1
            while check_idx >= 0:
                for open_m in cfg.existing_open_markers:
                    if lines[check_idx].strip().startswith(open_m):
                        return check_idx, comment_end_exclusive, base_indent
                check_idx -= 1
            # Couldn't find opening marker → treat as no existing comment
            return start_idx, start_idx, base_indent

        # --- Line comments (// or ///) ---
        if not cfg.existing_close_markers:
            # Line-comment languages (Go, Rust) – contiguous block of comment lines
            for open_m in cfg.existing_open_markers:
                if candidate.startswith(open_m):
                    comment_end_exclusive = check_idx + 1
                    while check_idx >= 0 and lines[check_idx].strip().startswith(open_m):
                        check_idx -= 1
                    return check_idx + 1, comment_end_exclusive, base_indent

        # No existing doc-comment found
        return start_idx, start_idx, base_indent
    
    def insert_docstrings(
        self,
        insertion_points: List[InsertionPoint]
    ) -> List[InsertionResult]:
        """
        Insert docstrings into source files.
        
        Args:
            insertion_points: List of prepared insertion points
            
        Returns:
            List of insertion results
        """
        results = []
        
        # Group insertions by file
        files_to_modify: Dict[str, List[InsertionPoint]] = {}
        for point in insertion_points:
            if point.file_path not in files_to_modify:
                files_to_modify[point.file_path] = []
            files_to_modify[point.file_path].append(point)
        
        for file_path, points in files_to_modify.items():
            file_results = self._process_file(file_path, points)
            results.extend(file_results)
        
        return results
    
    def _process_file(
        self,
        file_path_str: str,
        insertion_points: List[InsertionPoint]
    ) -> List[InsertionResult]:
        """Process a single file with multiple insertion points"""
        results = []
        
        # Handle both absolute and relative paths
        full_path = Path(file_path_str)
        
        if not full_path.exists():
            for point in insertion_points:
                results.append(InsertionResult(
                    component_id=point.component_id,
                    file_path=file_path_str,
                    success=False,
                    action='skipped',
                    message=f"File not found: {full_path}"
                ))
            return results
        
        try:
            # Read file content
            content = self.file_handler.read_file(full_path)
            lines = content.split('\n')
            
            # Create backup if enabled
            if self.backup:
                backup_path = full_path.with_suffix(full_path.suffix + '.bak')
                self.file_handler.write_file(backup_path, content)
            
            # Sort points by line number descending (process bottom-up)
            points_sorted = sorted(insertion_points, key=lambda x: -x.start_line)
            
            # Process each insertion point
            for point in points_sorted:
                insert_idx, existing_end_idx, base_indent = self._find_docstring_insert_position(
                    lines, point.start_line, point.component_type, point.language
                )
                
                has_existing = existing_end_idx > insert_idx
                
                if has_existing and not self.replace_existing:
                    results.append(InsertionResult(
                        component_id=point.component_id,
                        file_path=file_path_str,
                        success=True,
                        action='skipped',
                        message="Existing docstring preserved"
                    ))
                    continue
                
                # Format the new docstring with language-aware syntax
                docstring_lines = self._format_docstring(
                    point.docstring,
                    base_indent,
                    point.component_type,
                    point.language
                )
                
                if has_existing:
                    # Replace existing docstring
                    lines = lines[:insert_idx] + docstring_lines + lines[existing_end_idx:]
                    action = 'replaced'
                else:
                    # Insert new docstring
                    lines = lines[:insert_idx] + docstring_lines + lines[insert_idx:]
                    action = 'inserted'
                
                results.append(InsertionResult(
                    component_id=point.component_id,
                    file_path=file_path_str,
                    success=True,
                    action=action,
                    message=f"Docstring {action} at line {insert_idx + 1}"
                ))
            
            # Write modified content back
            new_content = '\n'.join(lines)
            self.file_handler.write_file(full_path, new_content)
            
            logger.info(f"Modified {full_path.name}: {len(points_sorted)} docstrings processed")
            
        except Exception as e:
            logger.error(f"Error processing {file_path_str}: {e}")
            for point in insertion_points:
                results.append(InsertionResult(
                    component_id=point.component_id,
                    file_path=file_path_str,
                    success=False,
                    action='error',
                    message=str(e)
                ))
        
        return results
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the full docstring insertion process.
        
        Returns:
            Summary of insertion results
        """
        logger.info("Starting docstring insertion process")
        
        # Load all writer outputs
        docstrings = self.load_writer_outputs()
        
        if not docstrings:
            logger.warning("No docstrings found to insert")
            return {'success': False, 'message': 'No docstrings found'}
        
        # Prepare insertion points
        insertion_points = self.prepare_insertions(docstrings)
        
        if not insertion_points:
            logger.warning("No valid insertion points found")
            return {'success': False, 'message': 'No valid insertion points'}
        
        # Insert docstrings
        results = self.insert_docstrings(insertion_points)
        
        # Summarize results
        summary = {
            'total': len(results),
            'inserted': sum(1 for r in results if r.action == 'inserted'),
            'replaced': sum(1 for r in results if r.action == 'replaced'),
            'skipped': sum(1 for r in results if r.action == 'skipped'),
            'errors': sum(1 for r in results if r.action == 'error'),
            'files_modified': len(set(r.file_path for r in results if r.success)),
            'results': [
                {
                    'component_id': r.component_id,
                    'file': r.file_path,
                    'action': r.action,
                    'success': r.success,
                    'message': r.message
                }
                for r in results
            ]
        }
        
        logger.info(
            f"Docstring insertion complete: "
            f"{summary['inserted']} inserted, "
            f"{summary['replaced']} replaced, "
            f"{summary['skipped']} skipped, "
            f"{summary['errors']} errors"
        )
        
        return summary


def insert_docstrings_to_source(
    writer_output_dir: str,
    component_data_file: str,
    backup: bool = True,
    replace_existing: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to insert docstrings into source files.
    
    Args:
        writer_output_dir: Directory containing writer output JSON files
        component_data_file: Path to component data JSON (reader output)
        backup: Whether to create backups
        replace_existing: Whether to replace existing docstrings
        
    Returns:
        Summary of insertion results
    """
    inserter = DocstringInserter(
        writer_output_dir=Path(writer_output_dir),
        component_data_file=Path(component_data_file),
        backup=backup,
        replace_existing=replace_existing
    )
    
    return inserter.run()


# ============================================================================
#  Standalone Docstring Generator (Meta-Inspired Dependency-First Approach)
# ============================================================================

# Minimum word count for an existing docstring to be considered "meaningful"
# Components with a docstring shorter than this are re-documented.
MIN_EXISTING_DOCSTRING_WORDS = 10


@dataclass
class GeneratorStats:
    """Tracks generation run statistics."""
    total: int = 0
    processed: int = 0
    skipped_existing: int = 0
    skipped_init: int = 0
    succeeded: int = 0
    failed: int = 0

    def __str__(self) -> str:
        return (
            f"Total={self.total}, Processed={self.processed}, "
            f"Succeeded={self.succeeded}, Failed={self.failed}, "
            f"SkippedExisting={self.skipped_existing}, "
            f"SkippedInit={self.skipped_init}"
        )


class DocstringGenerator:
    """
    Standalone docstring generator with dependency-based ordering.

    Mirrors the logic of Meta's ``generate_docstrings.py`` but is fully
    language-agnostic.  Uses the existing Navigator (``RepositoryParser``),
    topological ordering (``topo.py``), Orchestrator, and ``DocstringInserter``
    to process an entire repository.

    Ordering modes (inspired by Meta script):
      - ``topo`` (default): Dependency-first DFS – leaves (components with
        no dependencies) are processed first.
      - ``random_node``: Randomly shuffles all components.
      - ``random_file``: Files in random order, but preserves intra-file
        component ordering.

    Test modes:
      - ``none``: Normal operation – calls the LLM via the Orchestrator.
      - ``placeholder``: Generates lightweight placeholder docstrings
        without any LLM calls (useful for testing the pipeline).

    Usage::

        gen = DocstringGenerator(repo_path="backend/repos/myrepo")
        stats = gen.run()
    """

    def __init__(
        self,
        repo_path: str,
        order_mode: str = "topo",
        test_mode: str = "none",
        overwrite_existing: bool = False,
        backup: bool = True,
        min_docstring_words: int = MIN_EXISTING_DOCSTRING_WORDS,
    ):
        """
        Args:
            repo_path: Path to the repository root to document.
            order_mode: ``topo`` | ``random_node`` | ``random_file``.
            test_mode: ``none`` | ``placeholder``.
            overwrite_existing: When True, overwrite existing docstrings.
            backup: Create ``.bak`` files before modifying sources.
            min_docstring_words: Docstrings with fewer words than this threshold
                are treated as absent.
        """
        self.repo_path = repo_path
        self.order_mode = order_mode
        self.test_mode = test_mode
        self.overwrite_existing = overwrite_existing
        self.min_docstring_words = min_docstring_words

        self.inserter = DocstringInserter(
            backup=backup,
            replace_existing=overwrite_existing,
        )
        self.stats = GeneratorStats()

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def run(self) -> GeneratorStats:
        """
        Execute the full docstring generation pipeline.

        1. Parse repository → extract ``CodeComponent`` objects.
        2. Build dependency graph → resolve cycles.
        3. Order components according to ``order_mode``.
        4. For each component, generate (or placeholder) a docstring and
           insert it into the source file.

        Returns:
            ``GeneratorStats`` summarising the run.
        """
        from backend.navigator.core.repository_parser import RepositoryParser
        from backend.navigator.core.topo import (
            build_graph_from_components,
            resolve_cycles,
            dependency_first_dfs,
            topological_sort,
        )

        # Stage 1 – Parse
        logger.info(f"[DocstringGenerator] Parsing repository: {self.repo_path}")
        parser = RepositoryParser(self.repo_path)
        components: Dict[str, Any] = parser.parse()
        logger.info(f"[DocstringGenerator] Extracted {len(components)} components")

        if not components:
            logger.warning("[DocstringGenerator] No components found – nothing to do.")
            return self.stats

        # Stage 2 – Build & resolve graph
        logger.info("[DocstringGenerator] Building dependency graph …")
        graph = build_graph_from_components(components)
        graph = resolve_cycles(graph)

        # Stage 3 – Order
        ordered_ids = self._apply_ordering(graph, components)
        self.stats.total = len(ordered_ids)
        logger.info(
            f"[DocstringGenerator] Ordered {len(ordered_ids)} components "
            f"(mode={self.order_mode})"
        )

        # Build dependency-graph dict for orchestrator (id → list of dep ids)
        dep_graph: Dict[str, List[str]] = {
            cid: list(deps) for cid, deps in graph.items()
        }

        # Stage 4 – Initialise Orchestrator (unless placeholder mode)
        orchestrator = None
        if self.test_mode != "placeholder":
            try:
                from backend.agents.orchestrator.orchestrator import Orchestrator
                orchestrator = Orchestrator(project_dag=set(components.keys()))
            except Exception as exc:
                logger.error(f"[DocstringGenerator] Failed to init Orchestrator: {exc}")
                return self.stats

        # Stage 5 – Process each component
        for idx, component_id in enumerate(ordered_ids, 1):
            component = components.get(component_id)
            if component is None:
                logger.warning(f"Component {component_id} not found – skipping.")
                continue

            # Progress log
            lang_label = getattr(component, "language", "?")
            logger.info(
                f"[{idx}/{len(ordered_ids)}] {component_id} "
                f"({getattr(component, 'type', '?')}, {lang_label})"
            )

            # ---- skip rules ------------------------------------------------
            if self._should_skip(component, component_id):
                continue

            self.stats.processed += 1

            # ---- generate docstring -----------------------------------------
            try:
                if self.test_mode == "placeholder":
                    docstring = self._placeholder_docstring(component)
                else:
                    docstring = self._generate_via_orchestrator(
                        component, orchestrator, dep_graph
                    )

                if not docstring or not docstring.strip():
                    logger.warning(f"Empty docstring for {component_id}")
                    self.stats.failed += 1
                    continue

                # ---- insert into source file --------------------------------
                result = self._insert(component, docstring)
                if result.success:
                    self.stats.succeeded += 1
                    logger.info(f"  ✓ {result.action} for {component_id}")
                else:
                    self.stats.failed += 1
                    logger.warning(f"  ✗ {result.message}")

            except Exception as exc:
                logger.error(f"Error processing {component_id}: {exc}", exc_info=True)
                self.stats.failed += 1

        logger.info(f"[DocstringGenerator] Done – {self.stats}")
        return self.stats

    # ------------------------------------------------------------------
    #  Ordering
    # ------------------------------------------------------------------

    def _apply_ordering(
        self,
        graph: Dict[str, Set[str]],
        components: Dict[str, Any],
    ) -> List[str]:
        """
        Return component IDs in the order determined by ``self.order_mode``.
        """
        from backend.navigator.core.topo import dependency_first_dfs, topological_sort

        if self.order_mode == "topo":
            return dependency_first_dfs(graph)

        if self.order_mode == "random_node":
            ids = list(graph.keys())
            random.shuffle(ids)
            return ids

        if self.order_mode == "random_file":
            # Group by file, randomise file order, preserve intra-file order
            topo_ids = dependency_first_dfs(graph)
            file_groups: Dict[str, List[str]] = defaultdict(list)
            for cid in topo_ids:
                comp = components.get(cid)
                fp = ""
                if comp:
                    loc = getattr(comp, "location", None)
                    fp = getattr(loc, "file_path", "") if loc else ""
                file_groups[fp].append(cid)
            files = list(file_groups.keys())
            random.shuffle(files)
            result: List[str] = []
            for fp in files:
                result.extend(file_groups[fp])
            return result

        # Fallback
        return topological_sort(graph)

    # ------------------------------------------------------------------
    #  Skip logic
    # ------------------------------------------------------------------

    def _should_skip(self, component: Any, component_id: str) -> bool:
        """
        Decide whether to skip this component.

        Rules (mirroring Meta's script):
        1. Skip ``__init__`` / ``constructor`` methods.
        2. Skip components that already have a meaningful docstring
           (word count ≥ ``min_docstring_words``) unless ``overwrite_existing``
           is True.
        """
        comp_type = getattr(component, "type", None)
        comp_type_val = comp_type.value if hasattr(comp_type, "value") else str(comp_type)
        comp_name = getattr(component, "name", "")

        # Rule 1: Skip constructors / __init__
        if comp_type_val in ("method", "constructor") and comp_name in (
            "__init__", "constructor"
        ):
            logger.info(f"  → Skipping {component_id} (constructor)")
            self.stats.skipped_init += 1
            return True

        # Rule 2: Skip existing meaningful docstrings
        existing = getattr(component, "existing_docstring", None) or ""
        word_count = len(existing.split())
        if word_count >= self.min_docstring_words and not self.overwrite_existing:
            logger.info(
                f"  → Skipping {component_id} (existing docstring, "
                f"{word_count} words)"
            )
            self.stats.skipped_existing += 1
            return True

        return False

    # ------------------------------------------------------------------
    #  Docstring generation
    # ------------------------------------------------------------------

    def _placeholder_docstring(self, component: Any) -> str:
        """
        Generate language-aware placeholder docstring (no LLM call).

        Useful for testing the insertion pipeline end-to-end.
        """
        comp_type = getattr(component, "type", None)
        comp_type_val = comp_type.value if hasattr(comp_type, "value") else str(comp_type)
        name = getattr(component, "name", "unknown")
        language = getattr(component, "language", "python")

        if comp_type_val == "class":
            body = (
                f"Placeholder docstring for class '{name}'.\n"
                f"\n"
                f"This is a test placeholder generated without LLM calls.\n"
                f"Language: {language}"
            )
        elif comp_type_val == "method":
            body = (
                f"Placeholder docstring for method '{name}'.\n"
                f"\n"
                f"This is a test placeholder generated without LLM calls.\n"
                f"Language: {language}"
            )
        else:
            body = (
                f"Placeholder docstring for {comp_type_val} '{name}'.\n"
                f"\n"
                f"This is a test placeholder generated without LLM calls.\n"
                f"Language: {language}"
            )
        return body

    def _generate_via_orchestrator(
        self,
        component: Any,
        orchestrator: Any,
        dep_graph: Dict[str, List[str]],
    ) -> str:
        """
        Generate a real docstring via the multi-agent Orchestrator pipeline.

        Wraps the component in an ``AgentContext`` and drives the orchestrator's
        reader → searcher → writer loop.  Returns the raw writer output
        (the ``DocstringInserter.extract_docstring`` call is done later).
        """
        from backend.agents.base_agent import AgentContext
        from datetime import datetime

        context = AgentContext(
            component=component,
            metadata={
                "timestamp": datetime.now().isoformat(),
                "accumulated_context": {"internal": [], "external": []},
                "project_dag": orchestrator.project_dag if orchestrator else set(),
            },
        )

        # Run the reader–searcher–writer loop on this single component
        doc = orchestrator._process_with_searcher_writer_loop(
            component, context, {}
        )

        if doc is None:
            return ""

        # doc may be a Documentation object with a .docstring attribute
        raw = getattr(doc, "docstring", doc) if doc else ""
        return raw if isinstance(raw, str) else str(raw)

    # ------------------------------------------------------------------
    #  Insertion
    # ------------------------------------------------------------------

    def _insert(self, component: Any, docstring_text: str) -> InsertionResult:
        """
        Extract, clean, and insert a docstring for a single component.
        """
        # If the text looks like raw LLM output, extract from XML tags
        if "<DOCSTRING>" in docstring_text.upper():
            docstring_text = self.inserter.extract_docstring(docstring_text)
        docstring_text = self.inserter._clean_docstring_artifacts(docstring_text)

        if not docstring_text.strip():
            return InsertionResult(
                component_id=getattr(component, "id", "?"),
                file_path="",
                success=False,
                action="skipped",
                message="Empty after cleaning",
            )

        doc_data = {"docstring": docstring_text}
        return self.inserter.insert_for_component(component, doc_data)
